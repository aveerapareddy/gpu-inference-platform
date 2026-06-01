"""Lifecycle event emission (structured logs only)."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID

from gpu_inference_observability import LogContext, StructuredLogger


class LifecycleEventType(StrEnum):
    REQUEST_RECEIVED = "request_received"
    REQUEST_VALIDATED = "request_validated"
    REQUEST_ADMITTED = "request_admitted"
    REQUEST_QUEUED = "request_queued"
    REQUEST_REJECTED = "request_rejected"
    REQUEST_FAILED = "request_failed"
    REQUEST_COMPLETED = "request_completed"
    REQUEST_CREATED = "request_received"


class QueueEventType(StrEnum):
    REQUEST_ENQUEUED = "request_enqueued"
    REQUEST_DEQUEUED = "request_dequeued"
    QUEUE_FULL = "queue_full"
    QUEUE_TIMEOUT = "queue_timeout"
    QUEUE_REMOVED = "queue_removed"
    REQUEST_QUEUED = "request_queued"


class LifecycleEventEmitter:
    def __init__(self, logger: StructuredLogger, service_name: str) -> None:
        self._logger = logger
        self._service_name = service_name

    def emit(
        self,
        event_type: LifecycleEventType,
        request_id: UUID,
        *,
        correlation_id: str | None = None,
        lifecycle_state: str | None = None,
        timestamp: str | None = None,
        model: str | None = None,
        from_state: str | None = None,
        to_state: str | None = None,
        failure_reason: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        ctx = LogContext(
            service=self._service_name,
            request_id=request_id,
            trace_id=correlation_id,
            model=model,
        )
        fields: dict[str, Any] = {
            "event_type": event_type.value,
            "lifecycle_event": True,
        }
        if correlation_id is not None:
            fields["correlation_id"] = correlation_id
        if lifecycle_state is not None:
            fields["lifecycle_state"] = lifecycle_state
        if timestamp is not None:
            fields["timestamp"] = timestamp
        if from_state is not None:
            fields["from_state"] = from_state
        if to_state is not None:
            fields["to_state"] = to_state
        if failure_reason is not None:
            fields["failure_reason"] = failure_reason
        if extra:
            fields.update(extra)
        self._logger.info(event_type.value, ctx=ctx, **fields)

    def emit_queue(
        self,
        event_type: QueueEventType | LifecycleEventType,
        request_id: UUID,
        *,
        correlation_id: str | None = None,
        model: str | None = None,
        queue_position: int | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        ts = datetime.now(timezone.utc).isoformat()
        fields: dict[str, Any] = {
            "event_type": event_type.value,
            "queue_event": True,
            "timestamp": ts,
        }
        if correlation_id is not None:
            fields["correlation_id"] = correlation_id
        if queue_position is not None:
            fields["queue_position"] = queue_position
        if extra:
            fields.update(extra)
        ctx = LogContext(
            service=self._service_name,
            request_id=request_id,
            trace_id=correlation_id,
            model=model,
        )
        self._logger.info(event_type.value, ctx=ctx, **fields)
