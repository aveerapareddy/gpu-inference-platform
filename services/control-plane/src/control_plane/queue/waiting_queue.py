"""FIFO queue operations."""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from uuid import UUID

from common_schemas.states import PriorityClass

from control_plane.queue.capacity import QueueCapacityConfig, QueueCapacityDecision, evaluate_enqueue_capacity
from control_plane.queue.models import QueuedRequest, WaitingQueue, _default_queue_name
from control_plane.registry.models import RegisteredRequest


class QueueFullError(Exception):
    def __init__(self, reason: str = "queue_full", retry_after_ms: int = 250) -> None:
        self.reason = reason
        self.retry_after_ms = retry_after_ms
        super().__init__(reason)


class QueueOperations:
    """Deterministic FIFO queue. No scheduling or priority ordering."""

    def __init__(self, config: QueueCapacityConfig) -> None:
        config.validate()
        self._config = config
        self._waiting = WaitingQueue(max_size=config.max_queue_size, queue_timeout_ms=config.queue_timeout_ms)
        self._lock = threading.RLock()

    @property
    def config(self) -> QueueCapacityConfig:
        return self._config

    def enqueue(self, entry: RegisteredRequest) -> QueuedRequest:
        with self._lock:
            self._expire_timeouts_locked()
            if self.contains(entry.request_id):
                raise ValueError(f"request already queued: {entry.request_id}")

            capacity = evaluate_enqueue_capacity(
                current_depth=len(self._waiting.items),
                config=self._config,
            )
            if capacity.decision == QueueCapacityDecision.REJECT:
                raise QueueFullError(
                    capacity.reason or "queue_full",
                    retry_after_ms=capacity.retry_after_ms or 250,
                )

            now = datetime.now(timezone.utc)
            position = len(self._waiting.items) + 1
            priority = entry.inference_request.priority_class or PriorityClass.DEFAULT
            queued = QueuedRequest(
                request_id=entry.request_id,
                entry=entry,
                queue_entered_at=now,
                queue_position=position,
                queue_name=_default_queue_name(entry.inference_request.model),
                priority_class=priority,
            )
            self._waiting.items.append(queued)
            entry.queue_entered_at = now
            entry.queue_position = position
            return queued

    def dequeue(self) -> QueuedRequest | None:
        with self._lock:
            self._expire_timeouts_locked()
            if not self._waiting.items:
                return None
            item = self._waiting.items.pop(0)
            self._reindex_positions()
            return item

    def peek(self) -> QueuedRequest | None:
        with self._lock:
            self._expire_timeouts_locked()
            if not self._waiting.items:
                return None
            return self._waiting.items[0]

    def size(self) -> int:
        with self._lock:
            return len(self._waiting.items)

    def contains(self, request_id: UUID) -> bool:
        with self._lock:
            return any(item.request_id == request_id for item in self._waiting.items)

    def remove(self, request_id: UUID) -> QueuedRequest | None:
        with self._lock:
            for index, item in enumerate(self._waiting.items):
                if item.request_id == request_id:
                    removed = self._waiting.items.pop(index)
                    self._reindex_positions()
                    return removed
            return None

    def clear(self) -> int:
        with self._lock:
            count = len(self._waiting.items)
            self._waiting.items.clear()
            return count

    def list_items(self) -> list[QueuedRequest]:
        with self._lock:
            self._expire_timeouts_locked()
            return list(self._waiting.items)

    def expire_timeouts(self) -> list[QueuedRequest]:
        with self._lock:
            return self._expire_timeouts_locked()

    def _expire_timeouts_locked(self) -> list[QueuedRequest]:
        now = datetime.now(timezone.utc)
        expired: list[QueuedRequest] = []
        remaining: list[QueuedRequest] = []
        for item in self._waiting.items:
            wait_ms = (now - item.queue_entered_at).total_seconds() * 1000.0
            if wait_ms > self._config.queue_timeout_ms:
                expired.append(item)
            else:
                remaining.append(item)
        self._waiting.items = remaining
        self._reindex_positions()
        return expired

    def _reindex_positions(self) -> None:
        for index, item in enumerate(self._waiting.items, start=1):
            item.queue_position = index
            item.entry.queue_position = index
