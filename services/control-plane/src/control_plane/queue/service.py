"""Queue service: owns waiting workload between admission and scheduling."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from common_schemas.states import FailureReason, RequestState

from control_plane.failures.categories import AdmissionFailure
from control_plane.failures.framework import FailureFramework
from control_plane.observability.events import LifecycleEventEmitter, LifecycleEventType, QueueEventType
from control_plane.queue.capacity import QueueCapacityConfig
from control_plane.queue.inspection import QueueInspection, QueueSnapshot, QueueStatistics, QueuedRequestView
from control_plane.queue.waiting_queue import QueueFullError, QueueOperations
from control_plane.registry.memory import InMemoryRequestRegistry
from control_plane.registry.models import RegisteredRequest


class QueueService:
    """Accepts admitted requests into the waiting queue. Does not schedule."""

    def __init__(
        self,
        registry: InMemoryRequestRegistry,
        operations: QueueOperations,
        events: LifecycleEventEmitter,
    ) -> None:
        self._registry = registry
        self._ops = operations
        self._events = events
        self._inspection = QueueInspection(operations)

    @property
    def inspection(self) -> QueueInspection:
        return self._inspection

    def depth(self) -> int:
        return self._ops.size()

    def enqueue_from_admitted(self, request_id: UUID) -> RegisteredRequest:
        """ADMITTED -> QUEUED with queue ownership and timing."""
        entry = self._registry.get(request_id)
        if entry.state != RequestState.ADMITTED:
            raise ValueError(f"request {request_id} must be ADMITTED before enqueue, got {entry.state}")

        try:
            queued = self._ops.enqueue(entry)
        except QueueFullError as exc:
            self._events.emit_queue(
                QueueEventType.QUEUE_FULL,
                entry.request_id,
                correlation_id=entry.request_context.trace_id,
                model=entry.inference_request.model,
                queue_position=None,
                extra={"reason": exc.reason, "queue_depth": self._ops.size()},
            )
            failure = AdmissionFailure(exc.reason, reason=FailureReason.QUEUE_FULL, retryable=True)
            FailureFramework.apply_to_request(entry, failure.classified)
            entry.state = RequestState.REJECTED
            self._registry.update_state(request_id, RequestState.REJECTED)
            return entry

        entry.state = RequestState.QUEUED
        self._registry.update_state(request_id, RequestState.QUEUED)
        self._events.emit_queue(
            QueueEventType.REQUEST_ENQUEUED,
            entry.request_id,
            correlation_id=entry.request_context.trace_id,
            model=entry.inference_request.model,
            queue_position=queued.queue_position,
            extra={
                "queue_wait_duration_ms": 0.0,
                "request_age_ms": queued.request_age_ms,
                "queue_name": queued.queue_name,
            },
        )
        self._events.emit(
            LifecycleEventType.REQUEST_QUEUED,
            entry.request_id,
            correlation_id=entry.request_context.trace_id,
            lifecycle_state=RequestState.QUEUED.value,
            timestamp=datetime.now(timezone.utc).isoformat(),
            model=entry.inference_request.model,
            to_state=RequestState.QUEUED.value,
            extra={"queue_position": queued.queue_position},
        )
        return entry

    def dequeue_next(self) -> RegisteredRequest | None:
        """Remove head of queue. For future scheduler; updates no lifecycle state here."""
        item = self._ops.dequeue()
        if item is None:
            return None
        self._emit_dequeued(item)
        return item.entry

    def remove(self, request_id: UUID) -> RegisteredRequest | None:
        item = self._ops.remove(request_id)
        if item is None:
            return None
        self._events.emit_queue(
            QueueEventType.QUEUE_REMOVED,
            item.request_id,
            correlation_id=item.entry.request_context.trace_id,
            model=item.entry.inference_request.model,
            queue_position=item.queue_position,
        )
        return item.entry

    def process_timeouts(self) -> list[RegisteredRequest]:
        """Expire requests past queue_timeout_ms."""
        expired_items = self._ops.expire_timeouts()
        results: list[RegisteredRequest] = []
        for item in expired_items:
            entry = item.entry
            entry.state = RequestState.TIMED_OUT
            entry.failure_reason = FailureReason.QUEUE_TIMEOUT
            entry.failure_message = "queue wait timeout exceeded"
            self._registry.update_state(entry.request_id, RequestState.TIMED_OUT)
            self._events.emit_queue(
                QueueEventType.QUEUE_TIMEOUT,
                entry.request_id,
                correlation_id=entry.request_context.trace_id,
                model=entry.inference_request.model,
                queue_position=item.queue_position,
                extra={"queue_wait_duration_ms": item.queue_wait_duration_ms},
            )
            results.append(entry)
        return results

    def get_queue_snapshot(self, queue_name: str = "all") -> QueueSnapshot:
        return self._inspection.get_queue_snapshot(queue_name)

    def get_queue_statistics(self) -> QueueStatistics:
        return self._inspection.get_queue_statistics()

    def list_queued_requests(self) -> list[QueuedRequestView]:
        return self._inspection.list_queued_requests()

    def _emit_dequeued(self, item) -> None:
        self._events.emit_queue(
            QueueEventType.REQUEST_DEQUEUED,
            item.request_id,
            correlation_id=item.entry.request_context.trace_id,
            model=item.entry.inference_request.model,
            queue_position=item.queue_position,
            extra={
                "queue_wait_duration_ms": item.queue_wait_duration_ms,
                "request_age_ms": item.request_age_ms,
            },
        )
