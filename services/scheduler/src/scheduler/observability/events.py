"""Scheduler structured events (logs only)."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID

from gpu_inference_observability import LogContext, StructuredLogger
from gpu_inference_observability.runtime.models import RuntimeComponent, SchedulerEventRecord
from gpu_inference_observability.runtime.recorder import RuntimeEventRecorder


class SchedulerEventType(StrEnum):
    SCHEDULER_CYCLE_STARTED = "scheduler_cycle_started"
    SCHEDULER_CYCLE_COMPLETED = "scheduler_cycle_completed"
    REQUEST_SELECTED = "request_selected"
    REQUEST_SKIPPED = "request_skipped"
    SCHEDULER_FAILURE = "scheduler_failure"


class SchedulerEventEmitter:
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
        event_type: SchedulerEventType,
        *,
        scheduler_cycle_id: str | None = None,
        request_id: UUID | None = None,
        correlation_id: str | None = None,
        model: str | None = None,
        decision_reason: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        ts = datetime.now(timezone.utc).isoformat()
        fields: dict[str, Any] = {
            "event_type": event_type.value,
            "scheduler_event": True,
            "timestamp": ts,
        }
        if scheduler_cycle_id is not None:
            fields["scheduler_cycle_id"] = scheduler_cycle_id
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
            batch_id = (extra or {}).get("batch_id")
            self._recorder.record_scheduler(
                SchedulerEventRecord(
                    request_id=request_id,
                    correlation_id=correlation_id,
                    timestamp=recorded_at,
                    component=RuntimeComponent.SCHEDULER,
                    event_type=event_type.value,
                    scheduler_cycle_id=scheduler_cycle_id,
                    batch_id=batch_id,
                    decision_reason=decision_reason,
                    extra=extra or {},
                )
            )
