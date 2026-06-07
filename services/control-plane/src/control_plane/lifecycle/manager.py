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
from control_plane.queue.service import QueueService
from control_plane.registry.memory import InMemoryRequestRegistry
from control_plane.registry.models import RegisteredRequest
from control_plane.scheduler.client import SchedulerClient
from gpu_inference_observability.otel.helpers import optional_span
from gpu_inference_observability.otel.manager import TraceManager
from gpu_inference_observability.otel.spans import ComponentName, SpanName


class LifecycleManager:
    """Owns request state transitions. Does not schedule or execute inference."""

    def __init__(
        self,
        registry: InMemoryRequestRegistry,
        admission: AdmissionFramework,
        scheduler: SchedulerClient,
        events: LifecycleEventEmitter,
        queue: QueueService,
        *,
        trace_manager: TraceManager | None = None,
    ) -> None:
        self._registry = registry
        self._admission = admission
        self._scheduler = scheduler
        self._events = events
        self._queue = queue
        self._trace = trace_manager

    async def process_through_queued(self, submit: SubmitRequest) -> RegisteredRequest:
        """RECEIVED -> VALIDATED -> ADMITTED -> QUEUED. Stops at QUEUED."""
        request_id = submit.inference_request.request_id
        correlation_id = submit.request_context.trace_id
        model = submit.inference_request.model
        try:
            self._queue.process_timeouts()
            entry = self.register(submit, initial_state=RequestState.RECEIVED)
            with optional_span(
                self._trace,
                SpanName.VALIDATION,
                component=ComponentName.CONTROL_PLANE,
                request_id=request_id,
                correlation_id=correlation_id,
                model=model,
                request_state=RequestState.RECEIVED.value,
            ) as validation_scope:
                entry = self.transition(request_id, RequestState.VALIDATED)
                validation_scope.set_request_context(request_state=RequestState.VALIDATED.value)
            with optional_span(
                self._trace,
                SpanName.ADMISSION,
                component=ComponentName.CONTROL_PLANE,
                request_id=request_id,
                correlation_id=correlation_id,
                model=model,
                request_state=RequestState.VALIDATED.value,
            ) as admission_scope:
                entry = await self.run_admission(request_id)
                if entry.state == RequestState.REJECTED:
                    admission_scope.record_rejection(
                        entry.failure_message or "admission rejected",
                        failure_type="admission_rejected",
                    )
                    return entry
                admission_scope.set_request_context(request_state=RequestState.ADMITTED.value)
            if entry.state != RequestState.ADMITTED:
                raise InternalFailure(
                    f"unexpected state after admission: {entry.state.value}"
                )
            return self._queue.enqueue_from_admitted(request_id)
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

    def transition(
        self,
        request_id: UUID,
        to_state: RequestState,
        *,
        batch_id: UUID | None = None,
        backend_id: str | None = None,
    ) -> RegisteredRequest:
        entry = self._registry.get(request_id)
        if batch_id is not None:
            entry.batch_id = batch_id
        if backend_id is not None:
            entry.backend_id = backend_id
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
        *,
        batch_id: UUID | None = None,
        backend_id: str | None = None,
    ) -> RegisteredRequest:
        entry = self._registry.get(request_id)
        if batch_id is not None:
            entry.batch_id = batch_id
        if backend_id is not None:
            entry.backend_id = backend_id
        previous_state = entry.state
        failure = InternalFailure(message, reason=reason)
        target_state = FailureFramework.target_state(failure.classified)
        if is_allowed_transition(previous_state, target_state):
            updated = self.transition(request_id, target_state)
            FailureFramework.apply_to_request(updated, failure.classified)
            return updated
        FailureFramework.apply_to_request(entry, failure.classified)
        self._registry.update_state(request_id, target_state)
        self._emit_state_event(entry, LifecycleEventType.REQUEST_FAILED)
        return entry

    def complete_request(
        self,
        request_id: UUID,
        *,
        completion: InferenceCompletionRecord | None = None,
    ) -> RegisteredRequest:
        """SUBMITTED or STREAMING -> COMPLETED."""
        entry = self._registry.get(request_id)
        if entry.state not in {RequestState.SUBMITTED, RequestState.STREAMING}:
            raise InvalidTransitionError(str(request_id), entry.state, RequestState.COMPLETED)
        with optional_span(
            self._trace,
            SpanName.COMPLETION,
            component=ComponentName.CONTROL_PLANE,
            request_id=request_id,
            correlation_id=entry.request_context.trace_id,
            batch_id=entry.batch_id,
            backend_id=entry.backend_id,
            model=entry.inference_request.model,
            request_state=RequestState.SUBMITTED.value,
        ) as completion_scope:
            if completion is not None:
                entry.completion = completion
            updated = self.transition(request_id, RequestState.COMPLETED)
            completion_scope.set_request_context(request_state=RequestState.COMPLETED.value)
            extra = _trace_extra(updated)
            if completion is not None:
                extra.update(
                    {
                        "prompt_tokens": completion.prompt_tokens,
                        "completion_tokens": completion.completion_tokens,
                        "total_tokens": completion.total_tokens,
                        "finish_reason": completion.finish_reason,
                        "execution_duration_ms": completion.execution_duration_ms,
                    }
                )
            self._emit_state_event(
                updated,
                LifecycleEventType.REQUEST_COMPLETED,
                extra=extra,
            )
            return updated

    async def handoff_to_scheduler(self, request_id: UUID) -> RegisteredRequest:
        """No-op until scheduler exists."""
        entry = self._registry.get(request_id)
        await self._scheduler.submit_request(entry.submit)
        return entry

    def get_status(self, request_id: UUID) -> RequestState:
        return self._registry.get_status(request_id)

    def get_entry(self, request_id: UUID) -> RegisteredRequest:
        return self._registry.get(request_id)

    def _emit_state_event(
        self,
        entry: RegisteredRequest,
        event_type: LifecycleEventType,
        *,
        extra: dict | None = None,
    ) -> None:
        trace = _trace_extra(entry)
        if extra:
            trace.update(extra)
        self._events.emit(
            event_type,
            entry.request_id,
            correlation_id=entry.request_context.trace_id,
            lifecycle_state=entry.state.value,
            timestamp=datetime.now(timezone.utc).isoformat(),
            model=entry.inference_request.model,
            to_state=entry.state.value,
            extra=trace,
        )

    def _emit_for_transition(
        self,
        entry: RegisteredRequest,
        from_state: RequestState,
        to_state: RequestState,
    ) -> None:
        correlation_id = entry.request_context.trace_id
        ts = datetime.now(timezone.utc).isoformat()
        trace = _trace_extra(entry)
        common = {
            "correlation_id": correlation_id,
            "lifecycle_state": to_state.value,
            "timestamp": ts,
            "from_state": from_state.value,
            "to_state": to_state.value,
            "model": entry.inference_request.model,
            "extra": trace,
        }

        if to_state == RequestState.VALIDATED:
            self._events.emit(LifecycleEventType.REQUEST_VALIDATED, entry.request_id, **common)
        elif to_state == RequestState.ADMITTED:
            self._events.emit(LifecycleEventType.REQUEST_ADMITTED, entry.request_id, **common)
        elif to_state == RequestState.QUEUED:
            pass
        elif to_state == RequestState.SCHEDULED:
            self._events.emit(LifecycleEventType.REQUEST_SCHEDULED, entry.request_id, **common)
        elif to_state == RequestState.BATCHED:
            self._events.emit(LifecycleEventType.REQUEST_BATCHED, entry.request_id, **common)
        elif to_state == RequestState.SUBMITTED:
            self._events.emit(LifecycleEventType.REQUEST_SUBMITTED, entry.request_id, **common)
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


def _trace_extra(entry: RegisteredRequest) -> dict:
    extra: dict = {}
    if entry.batch_id is not None:
        extra["batch_id"] = str(entry.batch_id)
    if entry.backend_id is not None:
        extra["backend_id"] = entry.backend_id
    return extra
