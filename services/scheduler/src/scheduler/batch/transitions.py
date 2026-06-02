"""Batch state machine. Owner: scheduler batching engine."""

from __future__ import annotations

from scheduler.batch.models import BATCH_TERMINAL_STATES, BatchState


class InvalidBatchTransitionError(Exception):
    def __init__(self, from_state: BatchState, to_state: BatchState) -> None:
        self.from_state = from_state
        self.to_state = to_state
        super().__init__(f"invalid batch transition: {from_state.value} -> {to_state.value}")


ALLOWED_TRANSITIONS: dict[BatchState, frozenset[BatchState]] = {
    BatchState.CREATED: frozenset({BatchState.FILLING, BatchState.CANCELLED}),
    BatchState.FILLING: frozenset(
        {BatchState.FILLING, BatchState.READY, BatchState.CANCELLED, BatchState.FAILED}
    ),
    BatchState.READY: frozenset({BatchState.ACTIVE, BatchState.CANCELLED, BatchState.FAILED}),
    BatchState.ACTIVE: frozenset(
        {BatchState.ACTIVE, BatchState.COMPLETED, BatchState.FAILED, BatchState.CANCELLED}
    ),
    BatchState.COMPLETED: frozenset(),
    BatchState.FAILED: frozenset(),
    BatchState.CANCELLED: frozenset(),
}


def can_transition(from_state: BatchState, to_state: BatchState) -> bool:
    if from_state == to_state:
        return from_state in {BatchState.FILLING, BatchState.ACTIVE}
    if from_state in BATCH_TERMINAL_STATES:
        return False
    return to_state in ALLOWED_TRANSITIONS.get(from_state, frozenset())


def transition(from_state: BatchState, to_state: BatchState) -> BatchState:
    if not can_transition(from_state, to_state):
        raise InvalidBatchTransitionError(from_state, to_state)
    return to_state
