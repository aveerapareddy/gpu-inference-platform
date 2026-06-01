"""Queue inspection interfaces."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from common_schemas.queue import QueueItem

from control_plane.queue.models import QueueSnapshot, QueueStatistics, QueuedRequest
from control_plane.queue.waiting_queue import QueueOperations


@dataclass(frozen=True, slots=True)
class QueuedRequestView:
    request_id: str
    model: str
    correlation_id: str
    queue_position: int
    queue_entered_at: str
    queue_wait_duration_ms: float
    request_age_ms: float


class QueueInspection:
    def __init__(self, operations: QueueOperations) -> None:
        self._ops = operations

    def get_queue_snapshot(self, queue_name: str = "all") -> QueueSnapshot:
        items = self._ops.list_items()
        if queue_name != "all":
            items = [i for i in items if i.queue_name == queue_name]
        captured = datetime.now(timezone.utc).isoformat()
        return QueueSnapshot(
            queue_name=queue_name,
            depth=len(items),
            max_size=self._ops.config.max_queue_size,
            items=tuple(item.to_queue_item() for item in items),
            captured_at=captured,
        )

    def get_queue_statistics(self) -> QueueStatistics:
        items = self._ops.list_items()
        captured = datetime.now(timezone.utc).isoformat()
        if not items:
            return QueueStatistics(
                depth=0,
                max_size=self._ops.config.max_queue_size,
                oldest_wait_ms=None,
                average_wait_ms=None,
                captured_at=captured,
            )
        waits = [item.queue_wait_duration_ms for item in items]
        return QueueStatistics(
            depth=len(items),
            max_size=self._ops.config.max_queue_size,
            oldest_wait_ms=max(waits),
            average_wait_ms=sum(waits) / len(waits),
            captured_at=captured,
        )

    def list_queued_requests(self) -> list[QueuedRequestView]:
        return [_to_view(item) for item in self._ops.list_items()]


def _to_view(item: QueuedRequest) -> QueuedRequestView:
    return QueuedRequestView(
        request_id=str(item.request_id),
        model=item.entry.inference_request.model,
        correlation_id=item.entry.request_context.trace_id,
        queue_position=item.queue_position,
        queue_entered_at=item.queue_entered_at.isoformat(),
        queue_wait_duration_ms=item.queue_wait_duration_ms,
        request_age_ms=item.request_age_ms,
    )
