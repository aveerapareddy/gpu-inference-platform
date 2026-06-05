"""Durable persistence models. Owner: gpu_inference_observability.persistence."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from gpu_inference_observability.runtime.models import FailureRecord, RuntimeComponent, TraceEvent
from gpu_inference_observability.runtime.replay.models import (
    ExecutionComparison,
    LifecycleTransitionSnapshot,
    ReplayOutcome,
    ReplayResult,
    RequestExecutionRecord,
    RequestPayloadSnapshot,
    TerminalOutcome,
)


class FailureCategory(StrEnum):
    """Normalized failure category for query filters."""

    ADMISSION = "admission"
    QUEUE = "queue"
    SCHEDULER = "scheduler"
    BATCH = "batch"
    BACKEND = "backend"
    LIFECYCLE = "lifecycle"
    REPLAY = "replay"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class RequestMetadata:
    request_id: UUID
    correlation_id: str
    model: str | None
    terminal_state: str
    captured_at: datetime
    payload: RequestPayloadSnapshot
    terminal_outcome: TerminalOutcome


@dataclass(frozen=True, slots=True)
class LifecycleTransition:
    request_id: UUID
    sequence_num: int
    event_type: str
    from_state: str | None
    to_state: str | None
    timestamp: datetime


@dataclass(frozen=True, slots=True)
class SchedulerDecision:
    request_id: UUID
    sequence_num: int
    event_type: str
    decision_reason: str | None
    scheduler_cycle_id: str | None
    batch_id: str | None
    timestamp: datetime
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class BatchDecision:
    request_id: UUID
    sequence_num: int
    event_type: str
    batch_id: str | None
    decision_reason: str | None
    timestamp: datetime
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PersistedFailureRecord:
    failure_id: UUID
    request_id: UUID
    failure_type: str
    failure_owner: RuntimeComponent
    failure_component: str
    failure_category: FailureCategory
    failure_reason: str
    failure_state: str
    failure_timestamp: datetime
    correlation_id: str
    batch_id: str | None = None
    backend_id: str | None = None


@dataclass(frozen=True, slots=True)
class SpanMetadata:
    span_name: str
    component: str
    started_at: datetime | None = None
    ended_at: datetime | None = None
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TraceSummary:
    request_id: UUID
    correlation_id: str
    event_count: int
    failure_count: int
    stage_durations_ms: dict[str, float | None]
    span_metadata: tuple[SpanMetadata, ...]
    captured_at: datetime


@dataclass(frozen=True, slots=True)
class ReplayExecution:
    replay_id: UUID
    source_request_id: UUID | None
    replay_request_id: UUID
    outcome: ReplayOutcome
    terminal_state: str
    failure_reason: str | None
    failure_message: str | None
    started_at: datetime
    completed_at: datetime
    replay_events: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class ReplayComparisonRecord:
    comparison_id: UUID
    original_request_id: UUID
    replay_request_id: UUID
    generated_at: datetime
    terminal_state_match: bool
    matches: bool
    differences: tuple[dict[str, Any], ...]


def failure_category_from_record(record: FailureRecord) -> FailureCategory:
    owner = record.failure_owner
    if owner == RuntimeComponent.CONTROL_PLANE:
        if record.failure_type in {"queue_full", "queue_timeout"}:
            return FailureCategory.QUEUE
        if record.failure_type in {"admission_policy_failed", "request_rejected"}:
            return FailureCategory.ADMISSION
        return FailureCategory.LIFECYCLE
    if owner == RuntimeComponent.SCHEDULER:
        return FailureCategory.SCHEDULER
    if owner == RuntimeComponent.ADAPTER or owner == RuntimeComponent.BACKEND:
        return FailureCategory.BACKEND
    if owner == RuntimeComponent.REPLAY:
        return FailureCategory.REPLAY
    return FailureCategory.UNKNOWN


def lifecycle_transition_from_snapshot(
    request_id: UUID,
    sequence_num: int,
    snapshot: LifecycleTransitionSnapshot,
) -> LifecycleTransition:
    return LifecycleTransition(
        request_id=request_id,
        sequence_num=sequence_num,
        event_type=snapshot.event_type,
        from_state=snapshot.from_state,
        to_state=snapshot.to_state,
        timestamp=snapshot.timestamp,
    )


def scheduler_decision_from_event(request_id: UUID, sequence_num: int, event: TraceEvent) -> SchedulerDecision:
    extra = event.extra or {}
    return SchedulerDecision(
        request_id=request_id,
        sequence_num=sequence_num,
        event_type=event.event_type,
        decision_reason=event.decision_reason,
        scheduler_cycle_id=extra.get("scheduler_cycle_id"),
        batch_id=event.batch_id,
        timestamp=event.timestamp,
        details=extra,
    )


def batch_decision_from_event(request_id: UUID, sequence_num: int, event: TraceEvent) -> BatchDecision:
    return BatchDecision(
        request_id=request_id,
        sequence_num=sequence_num,
        event_type=event.event_type,
        batch_id=event.batch_id,
        decision_reason=event.decision_reason,
        timestamp=event.timestamp,
        details=event.extra or {},
    )


def persisted_failure_from_runtime(record: FailureRecord, failure_id: UUID | None = None) -> PersistedFailureRecord:
    from uuid import uuid4

    return PersistedFailureRecord(
        failure_id=failure_id or uuid4(),
        request_id=record.request_id,
        failure_type=record.failure_type,
        failure_owner=record.failure_owner,
        failure_component=record.failure_component,
        failure_category=failure_category_from_record(record),
        failure_reason=record.failure_reason,
        failure_state=record.failure_state,
        failure_timestamp=record.failure_timestamp,
        correlation_id=record.correlation_id,
        batch_id=record.batch_id,
        backend_id=record.backend_id,
    )


def replay_execution_from_result(result: ReplayResult, *, started_at: datetime, completed_at: datetime) -> ReplayExecution:
    return ReplayExecution(
        replay_id=result.replay_id,
        source_request_id=result.source_request_id,
        replay_request_id=result.replay_request_id,
        outcome=result.outcome,
        terminal_state=result.terminal_state,
        failure_reason=result.failure_reason,
        failure_message=result.failure_message,
        started_at=started_at,
        completed_at=completed_at,
        replay_events=result.replay_events,
    )


def replay_comparison_from_execution(comparison: ExecutionComparison, comparison_id: UUID) -> ReplayComparisonRecord:
    differences = tuple(
        {
            "kind": diff.kind.value,
            "field": diff.field,
            "original": diff.original,
            "replay": diff.replay,
            "detail": diff.detail,
        }
        for diff in comparison.differences
    )
    return ReplayComparisonRecord(
        comparison_id=comparison_id,
        original_request_id=comparison.original_request_id,
        replay_request_id=comparison.replay_request_id,
        generated_at=comparison.generated_at,
        terminal_state_match=comparison.terminal_state_match,
        matches=comparison.matches,
        differences=differences,
    )


def request_metadata_from_record(record: RequestExecutionRecord) -> RequestMetadata:
    model = record.payload.inference_request.get("model")
    return RequestMetadata(
        request_id=record.request_id,
        correlation_id=record.correlation_id,
        model=str(model) if model is not None else None,
        terminal_state=record.terminal_outcome.state,
        captured_at=record.captured_at,
        payload=record.payload,
        terminal_outcome=record.terminal_outcome,
    )
