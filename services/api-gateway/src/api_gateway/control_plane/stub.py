"""Legacy stub; superseded by integrated client when control plane is embedded."""

from __future__ import annotations

from uuid import UUID

from common_schemas.inference_request import ModelRecord, SubmitRequest
from common_schemas.states import RequestState

from api_gateway.control_plane.client import AcceptRequestResult
from api_gateway.errors import GatewayError
from common_schemas.states import FailureReason
from control_plane.registry.model_registry import default_model_registry

_MODEL_REGISTRY = default_model_registry()


class StubControlPlaneClient:
    """Model lookup only. Does not run lifecycle (use IntegratedControlPlaneClient)."""

    async def get_model(self, model_id: str) -> ModelRecord | None:
        return _MODEL_REGISTRY.get_model(model_id)

    async def is_ready(self) -> bool:
        return True

    async def accept_request(self, submit: SubmitRequest) -> AcceptRequestResult:
        raise GatewayError(
            error_type=FailureReason.INTERNAL_ERROR,
            message="control plane integration disabled",
            status_code=503,
        )

    async def get_request_status(self, request_id: UUID):
        raise NotImplementedError

    async def get_request_details(self, request_id: UUID):
        raise NotImplementedError

    async def list_active_requests(self):
        raise NotImplementedError

    async def list_requests_by_state(self, state: RequestState):
        raise NotImplementedError
