"""Registry read APIs."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from common_schemas.states import RequestState

from control_plane.registry.memory import InMemoryRequestRegistry
from control_plane.registry.models import RegisteredRequest


@dataclass(frozen=True, slots=True)
class RequestStatusView:
    request_id: UUID
    state: RequestState
    model: str
    correlation_id: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class RequestDetailsView:
    status: RequestStatusView
    entry: RegisteredRequest


class RegistryQueries:
    def __init__(self, registry: InMemoryRequestRegistry) -> None:
        self._registry = registry

    def get_status(self, request_id: UUID) -> RequestStatusView:
        entry = self._registry.get(request_id)
        return _to_status_view(entry)

    def get_details(self, request_id: UUID) -> RequestDetailsView:
        entry = self._registry.get(request_id)
        return RequestDetailsView(status=_to_status_view(entry), entry=entry)

    def list_active(self) -> list[RequestStatusView]:
        return [_to_status_view(e) for e in self._registry.list_active()]

    def list_by_state(self, state: RequestState) -> list[RequestStatusView]:
        return [_to_status_view(e) for e in self._registry.list_by_state(state)]


def _to_status_view(entry: RegisteredRequest) -> RequestStatusView:
    return RequestStatusView(
        request_id=entry.request_id,
        state=entry.state,
        model=entry.inference_request.model,
        correlation_id=entry.request_context.trace_id,
        updated_at=entry.updated_at.isoformat(),
    )
