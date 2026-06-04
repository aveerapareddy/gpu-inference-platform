"""Full request path orchestration across embedded services."""

from __future__ import annotations

from uuid import UUID

from common_schemas.inference_request import SubmitRequest
from common_schemas.states import FailureReason, RequestState, is_terminal_request_state

from api_gateway.runtime.stack import PlatformStack
from control_plane.errors import InvalidTransitionError
from control_plane.registry.models import RegisteredRequest
from gpu_inference_observability.otel.helpers import optional_span
from gpu_inference_observability.otel.spans import ComponentName, SpanName
from scheduler.models.batch_decision import BatchPlacementDecision, BatchRejectionDecision


class RequestPathOrchestrator:
    """Gateway → control plane → queue → scheduler → batch → adapter → mock completion."""

    def __init__(self, stack: PlatformStack) -> None:
        self._stack = stack

    @property
    def lifecycle(self):
        return self._stack.control_plane.lifecycle

    async def execute_full_path(self, submit: SubmitRequest) -> RegisteredRequest:
        request_id = submit.inference_request.request_id
        entry = await self.lifecycle.process_through_queued(submit)
        if is_terminal_request_state(entry.state):
            return entry
        if entry.state != RequestState.QUEUED:
            return entry

        trace = self._stack.trace_manager
        with optional_span(
            trace,
            SpanName.SCHEDULER,
            component=ComponentName.SCHEDULER,
            request_id=request_id,
            correlation_id=submit.request_context.trace_id,
            model=submit.inference_request.model,
            request_state=RequestState.QUEUED.value,
        ) as scheduler_scope:
            try:
                result = await self._stack.scheduler.run_scheduling_cycle()
            except Exception as exc:
                scheduler_scope.record_failure("scheduler_cycle_error", str(exc))
                raise
            finalized = self._finalize_request(request_id, result, submit)
            if finalized.state == RequestState.FAILED:
                scheduler_scope.record_failure(
                    finalized.failure_reason.value if finalized.failure_reason else "failed",
                    finalized.failure_message or "request_failed",
                )
            return finalized

    def _finalize_request(
        self,
        request_id: UUID,
        result,
        submit: SubmitRequest,
    ) -> RegisteredRequest:
        lifecycle = self.lifecycle
        batch_service = self._stack.scheduler.batch
        trace = self._stack.trace_manager
        correlation_id = submit.request_context.trace_id

        batch_rejection = _find_batch_rejection(result.rejection_decisions, request_id)
        if batch_rejection is not None:
            with optional_span(
                trace,
                SpanName.BATCH,
                component=ComponentName.SCHEDULER,
                request_id=request_id,
                correlation_id=correlation_id,
                batch_id=batch_rejection.batch_id,
                request_state=RequestState.QUEUED.value,
            ) as batch_scope:
                batch_scope.record_rejection(batch_rejection.decision_reason, failure_type="batch_rejected")
            return lifecycle.mark_failed(
                request_id,
                FailureReason.ADAPTER_ERROR,
                batch_rejection.decision_reason,
            )

        placement = _find_placement(result.placement_decisions, request_id)
        if placement is None:
            if request_id in result.skipped_request_ids:
                return lifecycle.get_entry(request_id)
            with optional_span(
                trace,
                SpanName.SCHEDULER,
                component=ComponentName.SCHEDULER,
                request_id=request_id,
                correlation_id=correlation_id,
                request_state=RequestState.QUEUED.value,
            ) as scheduler_scope:
                scheduler_scope.record_failure("scheduler_skip", "scheduler_did_not_select_request")
            return lifecycle.mark_failed(
                request_id,
                FailureReason.INTERNAL_ERROR,
                "scheduler_did_not_select_request",
            )

        entry = lifecycle.transition(
            request_id,
            RequestState.SCHEDULED,
            batch_id=placement.batch_id,
        )
        entry = lifecycle.transition(request_id, RequestState.BATCHED)

        dispatch = _find_dispatch(result.dispatch_results, placement.batch_id)
        if dispatch is None or not dispatch.accepted:
            reason = dispatch.reason if dispatch else "batch_not_dispatched"
            with optional_span(
                trace,
                SpanName.BACKEND_SUBMISSION,
                component=ComponentName.ADAPTER,
                request_id=request_id,
                correlation_id=correlation_id,
                batch_id=placement.batch_id,
                request_state=RequestState.BATCHED.value,
            ) as backend_scope:
                backend_scope.record_rejection(reason, failure_type="backend_rejected")
            return lifecycle.mark_failed(
                request_id,
                FailureReason.ADAPTER_ERROR,
                reason,
                batch_id=placement.batch_id,
            )

        entry = lifecycle.transition(
            request_id,
            RequestState.SUBMITTED,
            backend_id=dispatch.backend_id,
        )

        batch_service.complete_request(request_id)
        return lifecycle.complete_request(request_id)


def _find_placement(decisions, request_id: UUID) -> BatchPlacementDecision | None:
    for decision in decisions:
        if decision.request_id == request_id:
            return decision
    return None


def _find_batch_rejection(decisions, request_id: UUID) -> BatchRejectionDecision | None:
    for decision in decisions:
        if decision.request_id == request_id:
            return decision
    return None


def _find_dispatch(dispatch_results, batch_id: UUID):
    batch_key = str(batch_id)
    for dispatch in dispatch_results:
        if dispatch.batch_id == batch_key:
            return dispatch
    return None


class InvalidTransitionScenarioError(Exception):
    """Raised when integration validation expects a blocked transition."""

    def __init__(self, exc: InvalidTransitionError) -> None:
        self.transition_error = exc
        super().__init__(str(exc))
