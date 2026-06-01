"""Queue data structures. Owner: control plane queue service."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID

from common_schemas.queue import QueueItem
from common_schemas.states import PriorityClass

from control_plane.registry.models import RegisteredRequest


def _default_queue_name(model: str) -> str:
    return f"{model}/default"


@dataclass
class QueuedRequest:
    """In-memory queue entry with timing. Maps to common_schemas.QueueItem on export."""

    request_id: UUID
    entry: RegisteredRequest
    queue_entered_at: datetime
    queue_position: int
    queue_name: str
    priority_class: PriorityClass

    @property
    def request_age_ms(self) -> float:
        now = datetime.now(timezone.utc)
        return (now - self.entry.created_at).total_seconds() * 1000.0

    @property
    def queue_wait_duration_ms(self) -> float:
        now = datetime.now(timezone.utc)
        return (now - self.queue_entered_at).total_seconds() * 1000.0

    def to_queue_item(self) -> QueueItem:
        return QueueItem(
            request_id=self.request_id,
            inference_request=self.entry.inference_request,
            request_context=self.entry.request_context,
            enqueued_at=self.queue_entered_at,
            priority_class=self.priority_class,
            queue_name=self.queue_name,
        )


@dataclass
class WaitingQueue:
    """FIFO waiting queue. Not a scheduler; stores admitted workload only."""

    max_size: int
    queue_timeout_ms: int
    items: list[QueuedRequest] = field(default_factory=list)

    def queue_item_ids(self) -> list[UUID]:
        return [item.request_id for item in self.items]


@dataclass(frozen=True, slots=True)
class QueueSnapshot:
    """Point-in-time queue view."""

    queue_name: str
    depth: int
    max_size: int
    items: tuple[QueueItem, ...]
    captured_at: str


@dataclass(frozen=True, slots=True)
class QueueStatistics:
    """Aggregate queue metrics. No scheduling latency."""

    depth: int
    max_size: int
    oldest_wait_ms: float | None
    average_wait_ms: float | None
    captured_at: str
