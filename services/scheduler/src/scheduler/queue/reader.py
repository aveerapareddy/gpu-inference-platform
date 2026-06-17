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


def _estimate_input_tokens(item: QueueItem) -> int:
    total_chars = sum(len(message.content) for message in item.inference_request.messages)
    return max(1, total_chars // 4)


def queue_item_to_candidate(item: QueueItem, *, queue_position: int) -> SchedulingCandidate:
    now = datetime.now(timezone.utc)
    wait_ms = (now - item.enqueued_at).total_seconds() * 1000.0
    age_ms = (now - item.request_context.arrival_time).total_seconds() * 1000.0
    input_tokens = _estimate_input_tokens(item)
    max_tokens = item.inference_request.max_tokens
    priority = item.priority_class.value
    if item.inference_request.priority_class is not None:
        priority = item.inference_request.priority_class.value
    return SchedulingCandidate(
        request_id=item.request_id,
        model=item.inference_request.model,
        correlation_id=item.request_context.trace_id,
        queue_name=item.queue_name,
        queue_position=queue_position,
        queue_wait_duration_ms=wait_ms,
        enqueued_at=item.enqueued_at,
        max_tokens=max_tokens,
        estimated_input_tokens=input_tokens,
        estimated_job_tokens=input_tokens + max_tokens,
        priority_class=priority,
        request_age_ms=age_ms,
    )


def items_to_candidates(items: list[QueueItem]) -> list[SchedulingCandidate]:
    return [
        queue_item_to_candidate(item, queue_position=index)
        for index, item in enumerate(items, start=1)
    ]
