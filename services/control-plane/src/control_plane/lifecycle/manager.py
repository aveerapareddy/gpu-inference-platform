"""Request lifecycle ownership."""

from __future__ import annotations

from uuid import UUID

from common_schemas.inference_request import SubmitRequest
from common_schemas.states import RequestState, is_terminal_request_state

from control_plane.admission.framework import AdmissionFramework
from control_plane.admission.interfaces import AdmissionOutcome
from control_plane.failures.categories import AdmissionFailure
from control_plane.failures.framework import FailureFramework
from control_plane.errors import InvalidTransitionError
from control_plane.lifecycle.transitions import is_allowed_transition
from control_plane.observability.events import LifecycleEventEmitter, LifecycleEventType
from control_plane.registry.memory import InMemoryRequestRegistry
from control_plane.registry.models import RegisteredRequest
from control_plane.scheduler.client import SchedulerClient


class LifecycleManager:
    """Owns request state transitions. Does not schedule or execute inference."""

    def __init__(
        self,
        registry: InMemoryRequestRegistry,
        admission: AdmissionFramework,
        scheduler: SchedulerClient,
        events: LifecycleEventEmitter,
    ) -> None:
        self._registry = registry
        self._admission = admission
        self._scheduler = scheduler
        self._events = events

    def register(
        self,
        submit: SubmitRequest,
        *,
        initial_state: RequestState = RequestState.VALIDATED,
    ) -> RegisteredRequest:
        if initial_state not in {RequestState.RECEIVED, RequestState.VALIDATED}:
            raise InvalidTransitionError(
                str(submit.inference_request.request_id),
                RequestState.RECEIVED,
                initial_state,
            )
        entry = RegisteredRequest(submit=submit, state=initial_state)
        self._registry.register(entry)
        self._events.emit(
            LifecycleEventType.REQUEST_CREATED,
            entry.request_id,
            model=entry.inference_request.model,
            to_state=initial_state.value,
        )
        return entry

    def transition(self, request_id: UUID, to_state: RequestState) -> RegisteredRequest:
        entry = self._registry.get(request_id)
        from_state = entry.state
        if not is_allowed_transition(from_state, to_state):
            raise InvalidTransitionError(str(request_id), from_state, to_state)
        updated = self._registry.update_state(request_id, to_state)
        self._emit_for_transition(updated, from_state, to_state)
        if is_terminal_request_state(to_state):
            self._registry.remove(request_id)
        return updated

    async def run_admission(self, request_id: UUID) -> RegisteredRequest:
        """VALIDATED -> ADMITTED or REJECTED. No scheduler submit."""
        entry = self._registry.get(request_id)
        if entry.state != RequestState.VALIDATED:
            raise InvalidTransitionError(str(request_id), entry.state, RequestState.ADMITTED)

        result = await self._admission.evaluate(entry)
        if result.outcome == AdmissionOutcome.ACCEPT:
            return self.transition(request_id, RequestState.ADMITTED)
        failure = AdmissionFailure(
            result.reason or "admission rejected",
            retryable=result.retry_after_ms is not None,
        )
        FailureFramework.apply_to_request(entry, failure.classified)
        return self.transition(request_id, RequestState.REJECTED)

    async def handoff_to_scheduler(self, request_id: UUID) -> RegisteredRequest:
        """Extension point: submit to scheduler when connected. Session 5: no-op handoff."""
        entry = self._registry.get(request_id)
        await self._scheduler.submit_request(entry.submit)
        return entry

    def get_status(self, request_id: UUID) -> RequestState:
        return self._registry.get_status(request_id)

    def get_entry(self, request_id: UUID) -> RegisteredRequest:
        return self._registry.get(request_id)

    def _emit_for_transition(
        self,
        entry: RegisteredRequest,
        from_state: RequestState,
        to_state: RequestState,
    ) -> None:
        model = entry.inference_request.model
        rid = entry.request_id
        common = {"from_state": from_state.value, "to_state": to_state.value, "model": model}

        if to_state == RequestState.ADMITTED:
            self._events.emit(LifecycleEventType.REQUEST_ADMITTED, rid, **common)
        elif to_state == RequestState.QUEUED:
            self._events.emit(LifecycleEventType.REQUEST_QUEUED, rid, **common)
        elif to_state == RequestState.REJECTED:
            self._events.emit(
                LifecycleEventType.REQUEST_REJECTED,
                rid,
                failure_reason=entry.failure_reason.value if entry.failure_reason else None,
                **common,
            )
        elif to_state in {RequestState.FAILED, RequestState.TIMED_OUT}:
            self._events.emit(
                LifecycleEventType.REQUEST_FAILED,
                rid,
                failure_reason=entry.failure_reason.value if entry.failure_reason else None,
                **common,
            )
        elif to_state == RequestState.COMPLETED:
            self._events.emit(LifecycleEventType.REQUEST_COMPLETED, rid, **common)
