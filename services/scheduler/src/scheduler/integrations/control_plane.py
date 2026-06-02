"""Control plane queue integration."""

from __future__ import annotations

from common_schemas.queue import QueueItem

from scheduler.queue.reader import QueueSnapshotView


class ControlPlaneQueueReader:
    """Adapts control_plane.queue.QueueService for read-only scheduler access."""

    def __init__(self, queue_service) -> None:
        self._queue = queue_service

    def get_queue_snapshot(self, queue_name: str = "all") -> QueueSnapshotView:
        snapshot = self._queue.get_queue_snapshot(queue_name)
        return QueueSnapshotView(
            queue_name=snapshot.queue_name,
            depth=snapshot.depth,
            max_size=snapshot.max_size,
            items=snapshot.items,
            captured_at=snapshot.captured_at,
        )

    def list_queue_items(self, *, limit: int) -> list[QueueItem]:
        snapshot = self.get_queue_snapshot("all")
        return list(snapshot.items[:limit])
