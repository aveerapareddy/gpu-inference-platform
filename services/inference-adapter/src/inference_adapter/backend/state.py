"""Adapter backend process state. Owner: inference adapter.

Distinct from common_schemas.states.BackendState (worker membership lifecycle).
"""

from __future__ import annotations

from enum import StrEnum


class BackendState(StrEnum):
    UNKNOWN = "unknown"
    STARTING = "starting"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    STOPPED = "stopped"


BACKEND_TERMINAL_STATES: frozenset[BackendState] = frozenset({BackendState.STOPPED})

BACKEND_FAILURE_STATES: frozenset[BackendState] = frozenset(
    {BackendState.UNHEALTHY, BackendState.STOPPED}
)

ALLOWED_TRANSITIONS: dict[BackendState, frozenset[BackendState]] = {
    BackendState.UNKNOWN: frozenset({BackendState.STARTING, BackendState.STOPPED}),
    BackendState.STARTING: frozenset({BackendState.HEALTHY, BackendState.UNHEALTHY, BackendState.STOPPED}),
    BackendState.HEALTHY: frozenset({BackendState.DEGRADED, BackendState.UNHEALTHY, BackendState.STOPPED}),
    BackendState.DEGRADED: frozenset({BackendState.HEALTHY, BackendState.UNHEALTHY, BackendState.STOPPED}),
    BackendState.UNHEALTHY: frozenset({BackendState.STARTING, BackendState.STOPPED}),
    BackendState.STOPPED: frozenset(),
}


def can_transition(from_state: BackendState, to_state: BackendState) -> bool:
    if from_state == to_state:
        return True
    if from_state in BACKEND_TERMINAL_STATES:
        return False
    return to_state in ALLOWED_TRANSITIONS.get(from_state, frozenset())
