"""Shared control plane errors."""

from __future__ import annotations

from common_schemas.states import RequestState


class LifecycleError(Exception):
    """Base lifecycle error."""


class InvalidTransitionError(LifecycleError):
    def __init__(self, request_id: str, from_state: RequestState, to_state: RequestState) -> None:
        self.request_id = request_id
        self.from_state = from_state
        self.to_state = to_state
        super().__init__(
            f"invalid transition for {request_id}: {from_state.value} -> {to_state.value}"
        )


class RequestNotFoundError(LifecycleError):
    def __init__(self, request_id: str) -> None:
        self.request_id = request_id
        super().__init__(f"request not found: {request_id}")
