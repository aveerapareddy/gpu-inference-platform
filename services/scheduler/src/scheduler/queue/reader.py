"""Queue read interface for scheduler. Does not dequeue or mutate queue."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol
from uuid import UUID

from common_schemas.queue import QueueItem

from scheduler.models.decision import SchedulingCandidate


@dataclass(frozen=True, slots=True)
class QueueSnapshotView:
    queue_name: str
    depth: int
    max_size: int
    items: tuple[QueueItem, ...]
    captured_at: str


class QueueReader(Protocol):
    """Read-only queue access. Owner: control plane queue; scheduler consumes."""

    def get_queue_snapshot(self, queue_name: str = "all") -> QueueSnapshotView:
        """Return current queue contents without mutation."""

    def list_queue_items(self, *, limit: int) -> list[QueueItem]:
        """Return up to limit items in queue order (FIFO head first)."""


def queue_item_to_candidate(item: QueueItem, *, queue_position: int) -> SchedulingCandidate:
    now = datetime.now(timezone.utc)
    wait_ms = (now - item.enqueued_at).total_seconds() * 1000.0
    return SchedulingCandidate(
        request_id=item.request_id,
        model=item.inference_request.model,
        correlation_id=item.request_context.trace_id,
        queue_name=item.queue_name,
        queue_position=queue_position,
        queue_wait_duration_ms=wait_ms,
        enqueued_at=item.enqueued_at,
    )


def items_to_candidates(items: list[QueueItem]) -> list[SchedulingCandidate]:
    return [
        queue_item_to_candidate(item, queue_position=index)
        for index, item in enumerate(items, start=1)
    ]
