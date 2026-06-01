"""Control plane interface."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from common_schemas.inference_request import ModelRecord, SubmitRequest
from common_schemas.states import RequestState

from control_plane.registry.models import RegisteredRequest
from control_plane.registry.queries import RequestDetailsView, RequestStatusView


class AcceptRequestResult:
    """Outcome of gateway handoff to control plane."""

    __slots__ = ("entry", "state")

    def __init__(self, entry: RegisteredRequest) -> None:
        self.entry = entry
        self.state = entry.state


class ControlPlaneClient(Protocol):
    async def get_model(self, model_id: str) -> ModelRecord | None:
        """Return model record or None if unknown."""

    async def is_ready(self) -> bool:
        """True when control plane can accept requests."""

    async def accept_request(self, submit: SubmitRequest) -> AcceptRequestResult:
        """Register request and advance lifecycle through QUEUED."""

    async def get_request_status(self, request_id: UUID) -> RequestStatusView:
        ...

    async def get_request_details(self, request_id: UUID) -> RequestDetailsView:
        ...

    async def list_active_requests(self) -> list[RequestStatusView]:
        ...

    async def list_requests_by_state(self, state: RequestState) -> list[RequestStatusView]:
        ...
