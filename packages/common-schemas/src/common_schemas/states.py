"""Runtime state enumerations.

Status: Implemented (Session 3). Transition logic is not implemented.

Values match ``packages/common-schemas/schemas/enums.json`` and
``docs/contracts/state-models.md``.

Lifecycle ownership:
- RequestState: scheduler coordinates; gateway sets through validated.
- BatchState: scheduler creates; adapter updates execution phases.
- BackendState: adapter reports; control plane persists membership.
- SchedulerState: scheduler process aggregate mode only.
"""

from __future__ import annotations

from enum import StrEnum


class RequestState(StrEnum):
    RECEIVED = "received"
    VALIDATED = "validated"
    ADMITTED = "admitted"
    QUEUED = "queued"
    SCHEDULED = "scheduled"
    PREFILLING = "prefilling"
    DECODING = "decoding"
    STREAMING = "streaming"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


REQUEST_TERMINAL_STATES: frozenset[RequestState] = frozenset(
    {
        RequestState.COMPLETED,
        RequestState.FAILED,
        RequestState.TIMED_OUT,
        RequestState.REJECTED,
        RequestState.CANCELLED,
    }
)

REQUEST_FAILURE_STATES: frozenset[RequestState] = frozenset(
    {
        RequestState.FAILED,
        RequestState.TIMED_OUT,
        RequestState.REJECTED,
    }
)


class BatchState(StrEnum):
    FORMING = "forming"
    DISPATCHED = "dispatched"
    PREFILLING = "prefilling"
    DECODING = "decoding"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


BATCH_TERMINAL_STATES: frozenset[BatchState] = frozenset(
    {
        BatchState.COMPLETED,
        BatchState.FAILED,
        BatchState.CANCELLED,
    }
)

BATCH_FAILURE_STATES: frozenset[BatchState] = frozenset({BatchState.FAILED})


class BackendState(StrEnum):
    REGISTERING = "registering"
    IDLE = "idle"
    BUSY = "busy"
    DRAINING = "draining"
    UNHEALTHY = "unhealthy"
    OFFLINE = "offline"


BACKEND_TERMINAL_STATES: frozenset[BackendState] = frozenset(
    {
        BackendState.UNHEALTHY,
        BackendState.OFFLINE,
    }
)

BACKEND_FAILURE_STATES: frozenset[BackendState] = frozenset({BackendState.UNHEALTHY})


class SchedulerState(StrEnum):
    STARTING = "starting"
    ACCEPTING = "accepting"
    SATURATED = "saturated"
    DRAINING = "draining"
    UNAVAILABLE = "unavailable"


SCHEDULER_TERMINAL_STATES: frozenset[SchedulerState] = frozenset(
    {SchedulerState.UNAVAILABLE}
)

SCHEDULER_FAILURE_STATES: frozenset[SchedulerState] = frozenset(
    {SchedulerState.UNAVAILABLE}
)


class FailureReason(StrEnum):
    VALIDATION_ERROR = "validation_error"
    UNKNOWN_MODEL = "unknown_model"
    QUEUE_FULL = "queue_full"
    NO_CAPACITY = "no_capacity"
    QUEUE_TIMEOUT = "queue_timeout"
    PREFILL_TIMEOUT = "prefill_timeout"
    DECODE_TIMEOUT = "decode_timeout"
    E2E_TIMEOUT = "e2e_timeout"
    WORKER_ERROR = "worker_error"
    ADAPTER_ERROR = "adapter_error"
    INTERNAL_ERROR = "internal_error"
    CLIENT_CANCEL = "client_cancel"
    AUTHENTICATION_ERROR = "authentication_error"
    UNSUPPORTED_FIELD = "unsupported_field"


class FinishReason(StrEnum):
    STOP = "stop"
    LENGTH = "length"
    CANCELLED = "cancelled"
    ERROR = "error"


class TerminalStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class PriorityClass(StrEnum):
    DEFAULT = "default"
    ELEVATED = "elevated"
    BACKGROUND = "background"


class MessageRole(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class Component(StrEnum):
    GATEWAY = "gateway"
    CONTROL_PLANE = "control_plane"
    SCHEDULER = "scheduler"
    ADAPTER = "adapter"
    WORKER = "worker"


def is_terminal_request_state(state: RequestState) -> bool:
    return state in REQUEST_TERMINAL_STATES


def is_failure_request_state(state: RequestState) -> bool:
    return state in REQUEST_FAILURE_STATES
