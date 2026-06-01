"""Request lifecycle ownership."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from common_schemas.inference_request import SubmitRequest
from common_schemas.states import FailureReason, RequestState, is_terminal_request_state

from control_plane.admission.framework import AdmissionFramework
from control_plane.admission.interfaces import AdmissionOutcome
from control_plane.errors import InvalidTransitionError
from control_plane.failures.categories import AdmissionFailure, InternalFailure
from control_plane.failures.framework import FailureFramework
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

    async def process_through_queued(self, submit: SubmitRequest) -> RegisteredRequest:
        """RECEIVED -> VALIDATED -> ADMITTED -> QUEUED. Stops at QUEUED."""
        request_id = submit.inference_request.request_id
        try:
            entry = self.register(submit, initial_state=RequestState.RECEIVED)
            entry = self.transition(request_id, RequestState.VALIDATED)
            entry = await self.run_admission(request_id)
            if entry.state == RequestState.REJECTED:
                return entry
            if entry.state != RequestState.ADMITTED:
                raise InternalFailure(
                    f"unexpected state after admission: {entry.state.value}"
                )
            return self.transition(request_id, RequestState.QUEUED)
        except InvalidTransitionError:
            raise
        except InternalFailure:
            raise
        except Exception as exc:
            return self.mark_failed(
                request_id,
                FailureReason.INTERNAL_ERROR,
                f"control plane error: {exc}",
            )

    def register(
        self,
        submit: SubmitRequest,
        *,
        initial_state: RequestState = RequestState.RECEIVED,
    ) -> RegisteredRequest:
        if initial_state not in {RequestState.RECEIVED, RequestState.VALIDATED}:
            raise InvalidTransitionError(
                str(submit.inference_request.request_id),
                RequestState.RECEIVED,
                initial_state,
            )
        entry = RegisteredRequest(submit=submit, state=initial_state)
        self._registry.register(entry)
        if initial_state == RequestState.RECEIVED:
            self._emit_state_event(entry, LifecycleEventType.REQUEST_RECEIVED)
        else:
            self._emit_state_event(entry, LifecycleEventType.REQUEST_VALIDATED)
        return entry

    def transition(self, request_id: UUID, to_state: RequestState) -> RegisteredRequest:
        entry = self._registry.get(request_id)
        from_state = entry.state
        if not is_allowed_transition(from_state, to_state):
            raise InvalidTransitionError(str(request_id), from_state, to_state)
        updated = self._registry.update_state(request_id, to_state)
        self._emit_for_transition(updated, from_state, to_state)
        return updated

    async def run_admission(self, request_id: UUID) -> RegisteredRequest:
        """VALIDATED -> ADMITTED or REJECTED."""
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
        entry.state = RequestState.REJECTED
        self._registry.update_state(request_id, RequestState.REJECTED)
        self._emit_state_event(entry, LifecycleEventType.REQUEST_REJECTED)
        return entry

    def mark_failed(
        self,
        request_id: UUID,
        reason: FailureReason,
        message: str,
    ) -> RegisteredRequest:
        entry = self._registry.get(request_id)
        failure = InternalFailure(message, reason=reason)
        FailureFramework.apply_to_request(entry, failure.classified)
        if entry.state != RequestState.FAILED:
            if is_allowed_transition(entry.state, RequestState.FAILED):
                return self.transition(request_id, RequestState.FAILED)
            entry.state = RequestState.FAILED
            self._registry.update_state(request_id, RequestState.FAILED)
            self._emit_state_event(entry, LifecycleEventType.REQUEST_FAILED)
        return entry

    async def handoff_to_scheduler(self, request_id: UUID) -> RegisteredRequest:
        """No-op until scheduler exists."""
        entry = self._registry.get(request_id)
        await self._scheduler.submit_request(entry.submit)
        return entry

    def get_status(self, request_id: UUID) -> RequestState:
        return self._registry.get_status(request_id)

    def get_entry(self, request_id: UUID) -> RegisteredRequest:
        return self._registry.get(request_id)

    def _emit_state_event(self, entry: RegisteredRequest, event_type: LifecycleEventType) -> None:
        self._events.emit(
            event_type,
            entry.request_id,
            correlation_id=entry.request_context.trace_id,
            lifecycle_state=entry.state.value,
            timestamp=datetime.now(timezone.utc).isoformat(),
            model=entry.inference_request.model,
            to_state=entry.state.value,
        )

    def _emit_for_transition(
        self,
        entry: RegisteredRequest,
        from_state: RequestState,
        to_state: RequestState,
    ) -> None:
        correlation_id = entry.request_context.trace_id
        ts = datetime.now(timezone.utc).isoformat()
        common = {
            "correlation_id": correlation_id,
            "lifecycle_state": to_state.value,
            "timestamp": ts,
            "from_state": from_state.value,
            "to_state": to_state.value,
            "model": entry.inference_request.model,
        }

        if to_state == RequestState.VALIDATED:
            self._events.emit(LifecycleEventType.REQUEST_VALIDATED, entry.request_id, **common)
        elif to_state == RequestState.ADMITTED:
            self._events.emit(LifecycleEventType.REQUEST_ADMITTED, entry.request_id, **common)
        elif to_state == RequestState.QUEUED:
            self._events.emit(LifecycleEventType.REQUEST_QUEUED, entry.request_id, **common)
        elif to_state == RequestState.REJECTED:
            self._events.emit(
                LifecycleEventType.REQUEST_REJECTED,
                entry.request_id,
                failure_reason=entry.failure_reason.value if entry.failure_reason else None,
                **common,
            )
        elif to_state in {RequestState.FAILED, RequestState.TIMED_OUT}:
            self._events.emit(
                LifecycleEventType.REQUEST_FAILED,
                entry.request_id,
                failure_reason=entry.failure_reason.value if entry.failure_reason else None,
                **common,
            )
        elif to_state == RequestState.COMPLETED:
            self._events.emit(LifecycleEventType.REQUEST_COMPLETED, entry.request_id, **common)
