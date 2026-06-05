"""In-process platform integration for Session 11."""

from __future__ import annotations

from uuid import UUID

from common_schemas.inference_request import ModelRecord, SubmitRequest
from common_schemas.states import FailureReason, RequestState

from api_gateway.control_plane.client import AcceptRequestResult
from api_gateway.control_plane.stub import _STUB_MODELS
from api_gateway.errors import GatewayError
from api_gateway.runtime.orchestrator import RequestPathOrchestrator
from api_gateway.runtime.stack import PlatformStack
from control_plane.errors import InvalidTransitionError
from control_plane.failures.categories import PlatformFailure
from control_plane.registry.queries import RequestDetailsView, RequestStatusView
from gpu_inference_observability.otel.helpers import optional_span
from gpu_inference_observability.otel.spans import ComponentName, SpanName


class IntegratedPlatformClient:
    """Embeds control plane, scheduler, and inference adapter."""

    def __init__(self, stack: PlatformStack) -> None:
        self._stack = stack
        self._orchestrator = RequestPathOrchestrator(stack)

    @property
    def stack(self) -> PlatformStack:
        return self._stack

    async def get_model(self, model_id: str) -> ModelRecord | None:
        return _STUB_MODELS.get(model_id)

    async def is_ready(self) -> bool:
        return (
            self._stack.control_plane.is_running
            and self._stack.scheduler.is_running
            and self._stack.adapter.is_running
        )

    async def accept_request(self, submit: SubmitRequest) -> AcceptRequestResult:
        try:
            request_id = submit.inference_request.request_id
            correlation_id = submit.request_context.trace_id
            with optional_span(
                self._stack.trace_manager,
                SpanName.REQUEST,
                component=ComponentName.GATEWAY,
                request_id=request_id,
                correlation_id=correlation_id,
                model=submit.inference_request.model,
            ) as _request_scope:
                if self._stack.trace_recorder is not None:
                    self._stack.trace_recorder.record_gateway_receive(
                        request_id=request_id,
                        correlation_id=correlation_id,
                        extra={"model": submit.inference_request.model},
                    )
                entry = await self._orchestrator.execute_full_path(submit)
                if self._stack.replay_engine is not None:
                    self._stack.replay_engine.capture_from_entry(entry)
                _request_scope.set_request_context(request_state=entry.state.value)
                if entry.state == RequestState.REJECTED:
                    _raise_admission_error(entry)
                if entry.state == RequestState.FAILED:
                    _raise_execution_error(entry)
                if entry.state != RequestState.COMPLETED:
                    raise GatewayError(
                        error_type=FailureReason.INTERNAL_ERROR,
                        message=f"unexpected terminal state: {entry.state.value}",
                        status_code=500,
                    )
                return AcceptRequestResult(entry)
        except GatewayError:
            raise
        except InvalidTransitionError as exc:
            raise GatewayError(
                error_type=FailureReason.INTERNAL_ERROR,
                message=str(exc),
                status_code=500,
            ) from exc
        except PlatformFailure as exc:
            raise GatewayError(
                error_type=exc.classified.reason,
                message=exc.classified.message,
                status_code=500,
            ) from exc
        except Exception as exc:
            raise GatewayError(
                error_type=FailureReason.INTERNAL_ERROR,
                message=f"platform failure: {exc}",
                status_code=500,
            ) from exc

    async def get_request_status(self, request_id: UUID) -> RequestStatusView:
        return self._stack.control_plane.queries.get_status(request_id)

    async def get_request_details(self, request_id: UUID) -> RequestDetailsView:
        return self._stack.control_plane.queries.get_details(request_id)

    async def list_active_requests(self) -> list[RequestStatusView]:
        return self._stack.control_plane.queries.list_active()

    async def list_requests_by_state(self, state: RequestState) -> list[RequestStatusView]:
        return self._stack.control_plane.queries.list_by_state(state)


def _raise_admission_error(entry) -> None:
    reason = entry.failure_reason or FailureReason.QUEUE_FULL
    status = 429 if reason in {FailureReason.QUEUE_FULL, FailureReason.NO_CAPACITY} else 400
    retry_after_ms = 250 if status == 429 else None
    raise GatewayError(
        error_type=reason,
        message=entry.failure_message or reason.value,
        status_code=status,
        retry_after_ms=retry_after_ms,
    )


def _raise_execution_error(entry) -> None:
    reason = entry.failure_reason or FailureReason.ADAPTER_ERROR
    raise GatewayError(
        error_type=reason,
        message=entry.failure_message or reason.value,
        status_code=502,
    )
