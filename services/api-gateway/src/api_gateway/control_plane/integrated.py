"""In-process control plane integration for Session 6."""

from __future__ import annotations

from uuid import UUID

from common_schemas.inference_request import ModelRecord, SubmitRequest
from common_schemas.states import FailureReason, RequestState

from api_gateway.control_plane.client import AcceptRequestResult
from api_gateway.control_plane.stub import _MODEL_REGISTRY
from api_gateway.errors import GatewayError
from control_plane.application import ControlPlaneApplication
from control_plane.errors import InvalidTransitionError
from control_plane.failures.categories import PlatformFailure
from control_plane.registry.queries import RequestDetailsView, RequestStatusView


class IntegratedControlPlaneClient:
    """Embeds ControlPlaneApplication; no HTTP to control-plane service yet."""

    def __init__(self, application: ControlPlaneApplication) -> None:
        self._app = application

    async def get_model(self, model_id: str) -> ModelRecord | None:
        return self._app.model_registry.get_model(model_id)

    async def is_ready(self) -> bool:
        return self._app.is_running

    async def accept_request(self, submit: SubmitRequest) -> AcceptRequestResult:
        try:
            entry = await self._app.lifecycle.process_through_queued(submit)
            if entry.state == RequestState.REJECTED:
                _raise_admission_error(entry)
            if entry.state == RequestState.FAILED:
                _raise_internal_error(entry)
            if entry.state != RequestState.QUEUED:
                raise GatewayError(
                    error_type=FailureReason.INTERNAL_ERROR,
                    message=f"unexpected lifecycle state: {entry.state.value}",
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
                message=f"control plane failure: {exc}",
                status_code=500,
            ) from exc

    async def get_request_status(self, request_id: UUID) -> RequestStatusView:
        return self._app.queries.get_status(request_id)

    async def get_request_details(self, request_id: UUID) -> RequestDetailsView:
        return self._app.queries.get_details(request_id)

    async def list_active_requests(self) -> list[RequestStatusView]:
        return self._app.queries.list_active()

    async def list_requests_by_state(self, state: RequestState) -> list[RequestStatusView]:
        return self._app.queries.list_by_state(state)


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


def _raise_internal_error(entry) -> None:
    reason = entry.failure_reason or FailureReason.INTERNAL_ERROR
    raise GatewayError(
        error_type=reason,
        message=entry.failure_message or "control plane failure",
        status_code=500,
    )
