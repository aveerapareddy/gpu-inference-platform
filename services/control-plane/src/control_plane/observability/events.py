"""Lifecycle event emission (structured logs only)."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID

from gpu_inference_observability import LogContext, StructuredLogger
from gpu_inference_observability.runtime.models import (
    FailureEventRecord,
    LifecycleEventRecord,
    QueueEventRecord,
    RuntimeComponent,
)
from gpu_inference_observability.runtime.recorder import RuntimeEventRecorder
from gpu_inference_observability.registry.recorder import RuntimeMetricsRecorder


class LifecycleEventType(StrEnum):
    REQUEST_RECEIVED = "request_received"
    REQUEST_VALIDATED = "request_validated"
    REQUEST_ADMITTED = "request_admitted"
    REQUEST_QUEUED = "request_queued"
    REQUEST_SCHEDULED = "request_scheduled"
    REQUEST_BATCHED = "request_batched"
    REQUEST_SUBMITTED = "request_submitted"
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


def _parse_timestamp(timestamp: str | None) -> datetime:
    if timestamp is None:
        return datetime.now(timezone.utc)
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))


class LifecycleEventEmitter:
    def __init__(
        self,
        logger: StructuredLogger,
        service_name: str,
        *,
        trace_recorder: RuntimeEventRecorder | None = None,
        metrics_recorder: RuntimeMetricsRecorder | None = None,
    ) -> None:
        self._logger = logger
        self._service_name = service_name
        self._recorder = trace_recorder
        self._metrics = metrics_recorder

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
        if self._recorder is not None:
            ts = _parse_timestamp(timestamp)
            batch_id = (extra or {}).get("batch_id")
            backend_id = (extra or {}).get("backend_id")
            self._recorder.record_lifecycle(
                LifecycleEventRecord(
                    request_id=request_id,
                    correlation_id=correlation_id or "",
                    timestamp=ts,
                    component=RuntimeComponent.CONTROL_PLANE,
                    event_type=event_type.value,
                    lifecycle_state=lifecycle_state,
                    from_state=from_state,
                    to_state=to_state,
                    batch_id=batch_id,
                    backend_id=backend_id,
                    extra=extra or {},
                )
            )
            if failure_reason and event_type in {
                LifecycleEventType.REQUEST_FAILED,
                LifecycleEventType.REQUEST_REJECTED,
            }:
                self._recorder.record_failure(
                    FailureEventRecord(
                        request_id=request_id,
                        correlation_id=correlation_id or "",
                        timestamp=ts,
                        component=RuntimeComponent.CONTROL_PLANE,
                        event_type=event_type.value,
                        failure_type=event_type.value,
                        failure_reason=failure_reason,
                        failure_state=to_state or lifecycle_state or "unknown",
                        batch_id=batch_id,
                        backend_id=backend_id,
                    )
                )
        if self._metrics is not None:
            if event_type in {LifecycleEventType.REQUEST_RECEIVED, LifecycleEventType.REQUEST_CREATED}:
                self._metrics.record_request_received(request_id)
            elif event_type == LifecycleEventType.REQUEST_COMPLETED and from_state is not None:
                self._metrics.record_request_completed(request_id)
            elif event_type == LifecycleEventType.REQUEST_FAILED:
                self._metrics.record_request_failed(request_id)
            elif event_type == LifecycleEventType.REQUEST_REJECTED and from_state is not None:
                self._metrics.record_request_rejected(request_id)

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
        if self._recorder is not None:
            recorded_at = _parse_timestamp(ts)
            self._recorder.record_queue(
                QueueEventRecord(
                    request_id=request_id,
                    correlation_id=correlation_id or "",
                    timestamp=recorded_at,
                    component=RuntimeComponent.CONTROL_PLANE,
                    event_type=event_type.value,
                    queue_position=queue_position,
                    extra=extra or {},
                )
            )
            if event_type in {QueueEventType.QUEUE_FULL, QueueEventType.QUEUE_TIMEOUT}:
                reason = (extra or {}).get("reason", event_type.value)
                self._recorder.record_failure(
                    FailureEventRecord(
                        request_id=request_id,
                        correlation_id=correlation_id or "",
                        timestamp=recorded_at,
                        component=RuntimeComponent.CONTROL_PLANE,
                        event_type=event_type.value,
                        failure_type=event_type.value,
                        failure_reason=str(reason),
                        failure_state="rejected"
                        if event_type == QueueEventType.QUEUE_FULL
                        else "timed_out",
                    )
                )
        if self._metrics is not None:
            wait_ms = (extra or {}).get("queue_wait_duration_ms")
            wait_seconds = wait_ms / 1000.0 if wait_ms is not None else None
            if event_type == QueueEventType.REQUEST_ENQUEUED:
                self._metrics.record_queue_enqueue(wait_seconds=wait_seconds)
            elif event_type == QueueEventType.REQUEST_DEQUEUED:
                self._metrics.record_queue_dequeue(wait_seconds=wait_seconds)
            elif event_type == QueueEventType.QUEUE_TIMEOUT:
                self._metrics.record_queue_timeout(wait_seconds=wait_seconds)
                self._metrics.record_request_failed(request_id)
            elif event_type == QueueEventType.QUEUE_FULL:
                self._metrics.record_request_rejected(request_id)
