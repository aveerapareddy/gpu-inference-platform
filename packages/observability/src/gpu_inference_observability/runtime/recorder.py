"""Centralized runtime event recording."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from gpu_inference_observability.runtime.models import (
    BackendEventRecord,
    BatchEventRecord,
    FailureEventRecord,
    FailureRecord,
    LifecycleEventRecord,
    QueueEventRecord,
    RuntimeComponent,
    SchedulerEventRecord,
    TraceEvent,
)
from gpu_inference_observability.runtime.store import RequestTraceStore


class RuntimeEventRecorder:
    """Records structured events into RequestTraceStore."""

    def __init__(self, store: RequestTraceStore) -> None:
        self._store = store

    @property
    def store(self) -> RequestTraceStore:
        return self._store

    def record_lifecycle(
        self,
        record: LifecycleEventRecord,
    ) -> None:
        self._store.ensure(record.request_id, record.correlation_id)
        self._append_trace_event(
            request_id=record.request_id,
            correlation_id=record.correlation_id,
            timestamp=record.timestamp,
            component=record.component,
            event_type=record.event_type,
            lifecycle_state=record.to_state or record.lifecycle_state,
            batch_id=record.batch_id,
            backend_id=record.backend_id,
            extra={
                **record.extra,
                **({"from_state": record.from_state} if record.from_state else {}),
            },
        )

    def record_queue(self, record: QueueEventRecord) -> None:
        self._store.ensure(record.request_id, record.correlation_id)
        self._append_trace_event(
            request_id=record.request_id,
            correlation_id=record.correlation_id,
            timestamp=record.timestamp,
            component=record.component,
            event_type=record.event_type,
            batch_id=record.batch_id,
            backend_id=record.backend_id,
            extra={**record.extra, **({"queue_position": record.queue_position} if record.queue_position else {})},
        )

    def record_scheduler(self, record: SchedulerEventRecord) -> None:
        if record.request_id is not None and record.correlation_id:
            self._store.ensure(record.request_id, record.correlation_id)
        self._append_optional_event(record)

    def record_batch(self, record: BatchEventRecord) -> None:
        if record.request_id is not None and record.correlation_id:
            self._store.ensure(record.request_id, record.correlation_id)
        self._append_optional_event(record)

    def record_backend(self, record: BackendEventRecord) -> None:
        if record.request_id is not None and record.correlation_id:
            self._store.ensure(record.request_id, record.correlation_id)
        self._append_optional_event(record)

    def record_failure(self, record: FailureEventRecord) -> None:
        self._store.append_failure(
            FailureRecord(
                failure_type=record.failure_type,
                failure_owner=record.component,
                failure_component=record.component.value,
                failure_timestamp=record.timestamp,
                failure_reason=record.failure_reason,
                failure_state=record.failure_state,
                request_id=record.request_id,
                correlation_id=record.correlation_id,
                batch_id=record.batch_id,
                backend_id=record.backend_id,
            )
        )
        self._append_trace_event(
            request_id=record.request_id,
            correlation_id=record.correlation_id,
            timestamp=record.timestamp,
            component=record.component,
            event_type=record.event_type,
            lifecycle_state=record.failure_state,
            batch_id=record.batch_id,
            backend_id=record.backend_id,
            extra={"failure_type": record.failure_type, "failure_reason": record.failure_reason},
        )

    def record_gateway_receive(
        self,
        *,
        request_id: UUID,
        correlation_id: str,
        event_type: str = "gateway_request_received",
        extra: dict[str, Any] | None = None,
    ) -> None:
        ts = datetime.now(timezone.utc)
        self._store.ensure(request_id, correlation_id)
        self._append_trace_event(
            request_id=request_id,
            correlation_id=correlation_id,
            timestamp=ts,
            component=RuntimeComponent.GATEWAY,
            event_type=event_type,
            lifecycle_state="received",
            extra=extra or {},
        )

    def _append_optional_event(
        self,
        record: SchedulerEventRecord | BatchEventRecord | BackendEventRecord,
    ) -> None:
        if record.request_id is None:
            return
        correlation_id = record.correlation_id or ""
        self._append_trace_event(
            request_id=record.request_id,
            correlation_id=correlation_id,
            timestamp=record.timestamp,
            component=record.component,
            event_type=record.event_type,
            batch_id=record.batch_id,
            backend_id=record.backend_id,
            extra={
                **record.extra,
                **({"decision_reason": record.decision_reason} if record.decision_reason else {}),
                **(
                    {"scheduler_cycle_id": record.scheduler_cycle_id}
                    if isinstance(record, SchedulerEventRecord) and record.scheduler_cycle_id
                    else {}
                ),
            },
        )

    def _append_trace_event(
        self,
        *,
        request_id: UUID,
        correlation_id: str,
        timestamp: datetime,
        component: RuntimeComponent,
        event_type: str,
        lifecycle_state: str | None = None,
        batch_id: str | None = None,
        backend_id: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        self._store.append_event(
            TraceEvent(
                request_id=request_id,
                correlation_id=correlation_id,
                timestamp=timestamp,
                component=component,
                event_type=event_type,
                batch_id=batch_id,
                backend_id=backend_id,
                lifecycle_state=lifecycle_state,
                extra=extra or {},
            )
        )
