"""Batch lifecycle contracts. Owner: scheduler batching engine.

Distinct from common_schemas.batch.Batch (adapter dispatch unit).
These models track continuous batch membership before inference exists.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class BatchState(StrEnum):
    """Batch management lifecycle. No inference execution states."""

    CREATED = "created"
    FILLING = "filling"
    READY = "ready"
    ACTIVE = "active"
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


class MemberStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass
class BatchMember:
    request_id: UUID
    slot_index: int
    model: str
    correlation_id: str
    added_at: datetime
    status: MemberStatus = MemberStatus.ACTIVE


@dataclass
class BatchContext:
    """Runtime context for one managed batch."""

    batch_id: UUID
    model: str
    state: BatchState
    created_at: datetime
    admission_window_end: datetime
    activated_at: datetime | None = None
    completed_at: datetime | None = None
    failure_reason: str | None = None


@dataclass
class Batch:
    """Continuous batch with member tracking."""

    context: BatchContext
    members: list[BatchMember] = field(default_factory=list)

    @property
    def batch_id(self) -> UUID:
        return self.context.batch_id

    @property
    def state(self) -> BatchState:
        return self.context.state

    @property
    def active_member_count(self) -> int:
        return sum(1 for m in self.members if m.status == MemberStatus.ACTIVE)

    def active_members(self) -> list[BatchMember]:
        return [m for m in self.members if m.status == MemberStatus.ACTIVE]


@dataclass(frozen=True, slots=True)
class BatchResult:
    """Outcome of a batch operation (placement, retire, close)."""

    batch_id: UUID
    request_id: UUID | None
    success: bool
    decision_reason: str
    previous_state: BatchState | None = None
    new_state: BatchState | None = None


@dataclass(frozen=True, slots=True)
class BatchSnapshot:
    """Point-in-time batch view."""

    batch_id: UUID
    model: str
    state: BatchState
    member_count: int
    active_member_count: int
    members: tuple[BatchMember, ...]
    created_at: str
    captured_at: str


@dataclass(frozen=True, slots=True)
class BatchStatistics:
    """Aggregate batch metrics. No inference timing."""

    total_batches: int
    active_batches: int
    filling_batches: int
    total_active_requests: int
    total_completed_requests: int
    total_failed_requests: int
    total_cancelled_requests: int
    captured_at: str
