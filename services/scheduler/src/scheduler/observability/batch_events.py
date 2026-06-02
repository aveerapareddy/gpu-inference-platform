"""Batch structured events (logs only)."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID

from gpu_inference_observability import LogContext, StructuredLogger


class BatchEventType(StrEnum):
    BATCH_CREATED = "batch_created"
    BATCH_ADMISSION = "batch_admission"
    BATCH_FULL = "batch_full"
    REQUEST_ADDED_TO_BATCH = "request_added_to_batch"
    REQUEST_REMOVED_FROM_BATCH = "request_removed_from_batch"
    BATCH_COMPLETED = "batch_completed"
    BATCH_FAILED = "batch_failed"


class BatchEventEmitter:
    def __init__(self, logger: StructuredLogger, service_name: str) -> None:
        self._logger = logger
        self._service_name = service_name

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
