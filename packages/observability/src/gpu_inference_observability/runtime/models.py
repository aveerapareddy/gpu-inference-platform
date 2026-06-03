"""Runtime observability models. Owner: gpu_inference_observability.runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID


class RuntimeComponent(StrEnum):
    GATEWAY = "gateway"
    CONTROL_PLANE = "control_plane"
    SCHEDULER = "scheduler"
    ADAPTER = "adapter"
    BACKEND = "backend"


@dataclass(frozen=True, slots=True)
class TraceContext:
    """Per-request trace identifiers propagated across components."""

    request_id: UUID
    correlation_id: str
    batch_id: str | None = None
    backend_id: str | None = None


@dataclass(frozen=True, slots=True)
class TraceEvent:
    """Single recorded event on a request timeline."""

    request_id: UUID
    correlation_id: str
    timestamp: datetime
    component: RuntimeComponent
    event_type: str
    batch_id: str | None = None
    backend_id: str | None = None
    lifecycle_state: str | None = None
    decision_reason: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class TraceTimeline:
    """Ordered events with stage durations in milliseconds."""

    request_id: UUID
    correlation_id: str
    events: tuple[TraceEvent, ...]
    stage_durations_ms: dict[str, float | None]
    captured_at: datetime


@dataclass
class FailureRecord:
    failure_type: str
    failure_owner: RuntimeComponent
    failure_component: str
    failure_timestamp: datetime
    failure_reason: str
    failure_state: str
    request_id: UUID
    correlation_id: str
    batch_id: str | None = None
    backend_id: str | None = None


@dataclass
class LifecycleTimestamps:
    """Lifecycle stage timestamps. Units: UTC datetime."""

    request_received_at: datetime | None = None
    request_validated_at: datetime | None = None
    request_admitted_at: datetime | None = None
    request_queued_at: datetime | None = None
    request_scheduled_at: datetime | None = None
    request_batched_at: datetime | None = None
    request_submitted_at: datetime | None = None
    request_completed_at: datetime | None = None

    def record_lifecycle_state(self, state: str, ts: datetime) -> None:
        mapping = {
            "received": "request_received_at",
            "validated": "request_validated_at",
            "admitted": "request_admitted_at",
            "queued": "request_queued_at",
            "scheduled": "request_scheduled_at",
            "batched": "request_batched_at",
            "submitted": "request_submitted_at",
            "completed": "request_completed_at",
        }
        attr = mapping.get(state)
        if attr is not None:
            current = getattr(self, attr)
            if current is None:
                setattr(self, attr, ts)

    def durations_ms(self) -> dict[str, float | None]:
        def delta(start: datetime | None, end: datetime | None) -> float | None:
            if start is None or end is None:
                return None
            return (end - start).total_seconds() * 1000.0

        return {
            "validation_ms": delta(self.request_received_at, self.request_validated_at),
            "admission_ms": delta(self.request_validated_at, self.request_admitted_at),
            "queue_wait_ms": delta(self.request_admitted_at, self.request_queued_at),
            "schedule_ms": delta(self.request_queued_at, self.request_scheduled_at),
            "batch_ms": delta(self.request_scheduled_at, self.request_batched_at),
            "submit_ms": delta(self.request_batched_at, self.request_submitted_at),
            "completion_ms": delta(self.request_submitted_at, self.request_completed_at),
            "e2e_ms": delta(self.request_received_at, self.request_completed_at),
        }


@dataclass
class RequestTrace:
    """Complete trace for one request."""

    context: TraceContext
    events: list[TraceEvent] = field(default_factory=list)
    failures: list[FailureRecord] = field(default_factory=list)
    timestamps: LifecycleTimestamps = field(default_factory=LifecycleTimestamps)


@dataclass
class LifecycleEventRecord:
    request_id: UUID
    correlation_id: str
    timestamp: datetime
    component: RuntimeComponent
    event_type: str
    lifecycle_state: str | None = None
    from_state: str | None = None
    to_state: str | None = None
    batch_id: str | None = None
    backend_id: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class QueueEventRecord:
    request_id: UUID
    correlation_id: str
    timestamp: datetime
    component: RuntimeComponent
    event_type: str
    queue_position: int | None = None
    batch_id: str | None = None
    backend_id: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class SchedulerEventRecord:
    request_id: UUID | None
    correlation_id: str | None
    timestamp: datetime
    component: RuntimeComponent
    event_type: str
    scheduler_cycle_id: str | None = None
    batch_id: str | None = None
    backend_id: str | None = None
    decision_reason: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class BatchEventRecord:
    request_id: UUID | None
    correlation_id: str | None
    timestamp: datetime
    component: RuntimeComponent
    event_type: str
    batch_id: str | None = None
    backend_id: str | None = None
    decision_reason: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class BackendEventRecord:
    request_id: UUID | None
    correlation_id: str | None
    timestamp: datetime
    component: RuntimeComponent
    event_type: str
    batch_id: str | None = None
    backend_id: str | None = None
    decision_reason: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class FailureEventRecord:
    request_id: UUID
    correlation_id: str
    timestamp: datetime
    component: RuntimeComponent
    event_type: str
    failure_type: str
    failure_reason: str
    failure_state: str
    batch_id: str | None = None
    backend_id: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RequestMetrics:
    """Derived per-request metrics. Collection point: trace inspection."""

    request_id: UUID
    correlation_id: str
    validation_ms: float | None
    queue_wait_ms: float | None
    schedule_ms: float | None
    batch_ms: float | None
    submit_ms: float | None
    completion_ms: float | None
    e2e_ms: float | None
    event_count: int
    failure_count: int
    units: str = "milliseconds"


@dataclass(frozen=True, slots=True)
class QueueMetrics:
    request_id: UUID
    queue_event_count: int
    last_queue_position: int | None
    collection_point: str = "control_plane.queue"
    units: str = "count"


@dataclass(frozen=True, slots=True)
class SchedulerMetrics:
    request_id: UUID
    scheduler_event_count: int
    selected: bool
    collection_point: str = "scheduler.loop"
    units: str = "count"


@dataclass(frozen=True, slots=True)
class BatchMetrics:
    request_id: UUID
    batch_id: str | None
    batch_event_count: int
    collection_point: str = "scheduler.batch"
    units: str = "count"


@dataclass(frozen=True, slots=True)
class BackendMetrics:
    request_id: UUID
    backend_id: str | None
    batch_id: str | None
    backend_event_count: int
    accepted: bool | None
    collection_point: str = "inference_adapter"
    units: str = "count"
