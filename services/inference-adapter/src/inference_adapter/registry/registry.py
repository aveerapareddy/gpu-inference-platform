"""Backend registration and discovery. No routing logic."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone

from inference_adapter.backend.contract import InferenceBackend
from inference_adapter.backend.state import BackendState, can_transition


@dataclass
class RegisteredBackend:
    backend: InferenceBackend
    state: BackendState = BackendState.UNKNOWN
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_health_state: BackendState | None = None


class BackendRegistry:
    """In-memory backend registry."""

    def __init__(self) -> None:
        self._backends: dict[str, RegisteredBackend] = {}
        self._lock = threading.RLock()

    def register_backend(
        self,
        backend: InferenceBackend,
        *,
        initial_state: BackendState = BackendState.STARTING,
    ) -> None:
        with self._lock:
            backend_id = backend.backend_id
            if backend_id in self._backends:
                raise ValueError(f"backend already registered: {backend_id}")
            self._backends[backend_id] = RegisteredBackend(
                backend=backend,
                state=initial_state,
            )

    def remove_backend(self, backend_id: str) -> RegisteredBackend | None:
        with self._lock:
            entry = self._backends.pop(backend_id, None)
            if entry is not None:
                if can_transition(entry.state, BackendState.STOPPED):
                    entry.state = BackendState.STOPPED
            return entry

    def get_backend(self, backend_id: str) -> RegisteredBackend | None:
        with self._lock:
            return self._backends.get(backend_id)

    def list_backends(self) -> list[RegisteredBackend]:
        with self._lock:
            return list(self._backends.values())

    def set_state(self, backend_id: str, state: BackendState) -> None:
        with self._lock:
            entry = self._backends.get(backend_id)
            if entry is None:
                raise KeyError(f"backend not found: {backend_id}")
            if not can_transition(entry.state, state):
                raise ValueError(f"invalid state transition: {entry.state} -> {state}")
            entry.state = state
            entry.last_health_state = state

    def get_backend_instance(self, backend_id: str) -> InferenceBackend:
        entry = self.get_backend(backend_id)
        if entry is None:
            raise KeyError(f"backend not found: {backend_id}")
        return entry.backend
