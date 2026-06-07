"""Adapter-backed backend snapshot provider for routing."""

from __future__ import annotations

from common_schemas.routing import RoutableBackendSnapshot


class AdapterBackendProvider:
    def __init__(self, adapter) -> None:
        self._adapter = adapter

    def list_routable_backends(self) -> tuple[RoutableBackendSnapshot, ...]:
        return self._adapter.list_routable_backends()
