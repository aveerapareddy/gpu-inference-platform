"""In-memory request registry. Not durable."""

from __future__ import annotations

import threading
from uuid import UUID

from common_schemas.states import RequestState, is_terminal_request_state

from control_plane.errors import RequestNotFoundError
from control_plane.registry.models import RegisteredRequest


class InMemoryRequestRegistry:
    def __init__(self, max_entries: int = 10_000) -> None:
        self._max_entries = max_entries
        self._entries: dict[UUID, RegisteredRequest] = {}
        self._lock = threading.RLock()

    def register(self, entry: RegisteredRequest) -> RegisteredRequest:
        with self._lock:
            if len(self._entries) >= self._max_entries:
                raise RuntimeError("request registry at capacity")
            self._entries[entry.request_id] = entry
            return entry

    def get(self, request_id: UUID) -> RegisteredRequest:
        with self._lock:
            entry = self._entries.get(request_id)
            if entry is None:
                raise RequestNotFoundError(str(request_id))
            return entry

    def update_state(self, request_id: UUID, state: RequestState) -> RegisteredRequest:
        with self._lock:
            entry = self.get(request_id)
            entry.state = state
            from datetime import datetime, timezone

            entry.updated_at = datetime.now(timezone.utc)
            return entry

    def get_status(self, request_id: UUID) -> RequestState:
        return self.get(request_id).state

    def remove(self, request_id: UUID) -> None:
        with self._lock:
            self._entries.pop(request_id, None)

    def remove_if_terminal(self, request_id: UUID) -> bool:
        with self._lock:
            entry = self._entries.get(request_id)
            if entry is None:
                return False
            if is_terminal_request_state(entry.state):
                del self._entries[request_id]
                return True
            return False

    def count(self) -> int:
        with self._lock:
            return len(self._entries)

    def list_active(self) -> list[RegisteredRequest]:
        """Non-terminal requests currently owned by the control plane."""
        with self._lock:
            return [
                entry
                for entry in self._entries.values()
                if not is_terminal_request_state(entry.state)
            ]

    def list_by_state(self, state: RequestState) -> list[RegisteredRequest]:
        with self._lock:
            return [entry for entry in self._entries.values() if entry.state == state]
