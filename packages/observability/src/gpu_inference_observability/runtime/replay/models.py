"""Replay domain models. Owner: gpu_inference_observability.runtime.replay."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID

from gpu_inference_observability.runtime.models import FailureRecord, TraceEvent


@dataclass(frozen=True, slots=True)
class RequestPayloadSnapshot:
    """Immutable request payload for replay. JSON-serializable dicts."""

    inference_request: dict[str, Any]
    request_context: dict[str, Any]

    @classmethod
    def from_submit(cls, submit: Any) -> RequestPayloadSnapshot:
        return cls(
            inference_request=submit.inference_request.model_dump(),
            request_context=submit.request_context.model_dump(),
        )


@dataclass(frozen=True, slots=True)
class TerminalOutcome:
    state: str
    failure_reason: str | None = None
    failure_message: str | None = None
    batch_id: str | None = None
    backend_id: str | None = None


@dataclass(frozen=True, slots=True)
class LifecycleTransitionSnapshot:
    event_type: str
    from_state: str | None
    to_state: str | None
    timestamp: datetime


@dataclass
class RequestExecutionRecord:
    """Source of truth for replay. Captured at terminal state."""

    request_id: UUID
    correlation_id: str
    captured_at: datetime
    payload: RequestPayloadSnapshot
    lifecycle_transitions: tuple[LifecycleTransitionSnapshot, ...]
    queue_events: tuple[TraceEvent, ...]
    scheduler_events: tuple[TraceEvent, ...]
    batch_events: tuple[TraceEvent, ...]
    backend_events: tuple[TraceEvent, ...]
    failures: tuple[FailureRecord, ...]
    terminal_outcome: TerminalOutcome
    event_timeline: tuple[TraceEvent, ...]
    replay_id: UUID | None = None
    source_request_id: UUID | None = None
    completion: Any | None = None


@dataclass(frozen=True, slots=True)
class ReplayContext:
    replay_id: UUID
    source_request_id: UUID
    source_correlation_id: str
    started_at: datetime


class ReplayOutcome(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"
    TIMED_OUT = "timed_out"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class ReplayRequest:
    """Replay input: from execution record or payload snapshot."""

    replay_id: UUID
    payload: RequestPayloadSnapshot
    source_request_id: UUID | None = None
    source_record: RequestExecutionRecord | None = None


@dataclass
class ReplayResult:
    replay_id: UUID
    source_request_id: UUID | None
    replay_request_id: UUID
    outcome: ReplayOutcome
    terminal_state: str
    failure_reason: str | None
    failure_message: str | None
    execution_record: RequestExecutionRecord | None
    replay_events: tuple[str, ...] = field(default_factory=tuple)
    error: str | None = None


class ExecutionDifferenceKind(StrEnum):
    LIFECYCLE = "lifecycle"
    SCHEDULER = "scheduler"
    BATCH = "batch"
    BACKEND = "backend"
    TERMINAL = "terminal"
    EVENT_SEQUENCE = "event_sequence"


@dataclass(frozen=True, slots=True)
class ExecutionDifference:
    kind: ExecutionDifferenceKind
    field: str
    original: str | None
    replay: str | None
    detail: str | None = None


@dataclass
class ExecutionComparison:
    original_request_id: UUID
    replay_request_id: UUID
    generated_at: datetime
    terminal_state_match: bool
    differences: tuple[ExecutionDifference, ...]
    original_terminal_state: str
    replay_terminal_state: str

    @property
    def matches(self) -> bool:
        return not self.differences


@dataclass
class ReconstructedExecution:
    """Deterministic debugging view for one request."""

    request_id: UUID
    correlation_id: str
    payload: RequestPayloadSnapshot
    lifecycle_history: tuple[LifecycleTransitionSnapshot, ...]
    scheduler_decisions: tuple[TraceEvent, ...]
    batch_history: tuple[TraceEvent, ...]
    backend_interactions: tuple[TraceEvent, ...]
    queue_events: tuple[TraceEvent, ...]
    failures: tuple[FailureRecord, ...]
    terminal_outcome: TerminalOutcome | None
    event_timeline: tuple[TraceEvent, ...]
    captured_at: datetime | None = None


def replay_outcome_from_state(state: str) -> ReplayOutcome:
    if state == "completed":
        return ReplayOutcome.COMPLETED
    if state == "rejected":
        return ReplayOutcome.REJECTED
    if state == "timed_out":
        return ReplayOutcome.TIMED_OUT
    if state == "failed":
        return ReplayOutcome.FAILED
    return ReplayOutcome.ERROR


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
