"""Allowed RequestState transitions per docs/contracts/state-models.md."""

from __future__ import annotations

from common_schemas.states import RequestState

ALLOWED_REQUEST_TRANSITIONS: dict[RequestState, frozenset[RequestState]] = {
    RequestState.RECEIVED: frozenset(
        {RequestState.VALIDATED, RequestState.CANCELLED, RequestState.FAILED}
    ),
    RequestState.VALIDATED: frozenset(
        {RequestState.ADMITTED, RequestState.REJECTED, RequestState.CANCELLED}
    ),
    RequestState.ADMITTED: frozenset(
        {
            RequestState.QUEUED,
            RequestState.SCHEDULED,
            RequestState.REJECTED,
            RequestState.CANCELLED,
            RequestState.FAILED,
        }
    ),
    RequestState.QUEUED: frozenset(
        {
            RequestState.SCHEDULED,
            RequestState.REJECTED,
            RequestState.TIMED_OUT,
            RequestState.CANCELLED,
        }
    ),
    RequestState.SCHEDULED: frozenset(
        {
            RequestState.PREFILLING,
            RequestState.FAILED,
            RequestState.TIMED_OUT,
            RequestState.CANCELLED,
        }
    ),
    RequestState.PREFILLING: frozenset(
        {
            RequestState.DECODING,
            RequestState.FAILED,
            RequestState.TIMED_OUT,
            RequestState.CANCELLED,
        }
    ),
    RequestState.DECODING: frozenset(
        {
            RequestState.STREAMING,
            RequestState.COMPLETED,
            RequestState.FAILED,
            RequestState.TIMED_OUT,
            RequestState.CANCELLED,
        }
    ),
    RequestState.STREAMING: frozenset(
        {
            RequestState.COMPLETED,
            RequestState.CANCELLED,
            RequestState.FAILED,
        }
    ),
}


def is_allowed_transition(from_state: RequestState, to_state: RequestState) -> bool:
    if from_state in {RequestState.COMPLETED, RequestState.FAILED, RequestState.TIMED_OUT,
                      RequestState.REJECTED, RequestState.CANCELLED}:
        return False
    allowed = ALLOWED_REQUEST_TRANSITIONS.get(from_state, frozenset())
    return to_state in allowed
