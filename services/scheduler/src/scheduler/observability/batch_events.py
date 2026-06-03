"""Batch structured events (logs only)."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID

from gpu_inference_observability import LogContext, StructuredLogger
from gpu_inference_observability.runtime.models import BatchEventRecord, RuntimeComponent
from gpu_inference_observability.runtime.recorder import RuntimeEventRecorder


class BatchEventType(StrEnum):
    BATCH_CREATED = "batch_created"
    BATCH_ADMISSION = "batch_admission"
    BATCH_FULL = "batch_full"
    REQUEST_ADDED_TO_BATCH = "request_added_to_batch"
    REQUEST_REMOVED_FROM_BATCH = "request_removed_from_batch"
    BATCH_COMPLETED = "batch_completed"
    BATCH_FAILED = "batch_failed"


class BatchEventEmitter:
    def __init__(
        self,
        logger: StructuredLogger,
        service_name: str,
        *,
        trace_recorder: RuntimeEventRecorder | None = None,
    ) -> None:
        self._logger = logger
        self._service_name = service_name
        self._recorder = trace_recorder

    def emit(
        self,
        event_type: BatchEventType,
        *,
        batch_id: UUID | None = None,
        request_id: UUID | None = None,
        correlation_id: str | None = None,
        model: str | None = None,
        decision_reason: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        ts = datetime.now(timezone.utc).isoformat()
        fields: dict[str, Any] = {
            "event_type": event_type.value,
            "batch_event": True,
            "timestamp": ts,
        }
        if batch_id is not None:
            fields["batch_id"] = str(batch_id)
        if decision_reason is not None:
            fields["decision_reason"] = decision_reason
        if extra:
            fields.update(extra)

        ctx = LogContext(
            service=self._service_name,
            request_id=request_id,
            trace_id=correlation_id,
            model=model,
        )
        self._logger.info(event_type.value, ctx=ctx, **fields)
        if self._recorder is not None and request_id is not None:
            recorded_at = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            self._recorder.record_batch(
                BatchEventRecord(
                    request_id=request_id,
                    correlation_id=correlation_id,
                    timestamp=recorded_at,
                    component=RuntimeComponent.SCHEDULER,
                    event_type=event_type.value,
                    batch_id=str(batch_id) if batch_id is not None else None,
                    decision_reason=decision_reason,
                    extra=extra or {},
                )
            )
