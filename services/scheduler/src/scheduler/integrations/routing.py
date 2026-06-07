"""Routing port for scheduler dispatch."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from common_schemas.routing import RoutingResult


class RoutingEnginePort(Protocol):
    def route(
        self,
        *,
        request_id: UUID,
        model_id: str,
        excluded_backend_ids: frozenset[str] = frozenset(),
    ) -> RoutingResult: ...
