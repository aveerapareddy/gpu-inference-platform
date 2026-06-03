"""Adapter structured events (logs only)."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID

from gpu_inference_observability import LogContext, StructuredLogger
from gpu_inference_observability.runtime.models import (
    BackendEventRecord,
    FailureEventRecord,
    RuntimeComponent,
)
from gpu_inference_observability.runtime.recorder import RuntimeEventRecorder


class BackendEventType(StrEnum):
    BACKEND_REGISTERED = "backend_registered"
    BACKEND_REMOVED = "backend_removed"
    BACKEND_SELECTED = "backend_selected"
    BATCH_SUBMITTED = "batch_submitted"
    BATCH_ACCEPTED = "batch_accepted"
    BATCH_REJECTED = "batch_rejected"
    BACKEND_HEALTH_CHANGED = "backend_health_changed"


class BackendEventEmitter:
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
        event_type: BackendEventType,
        *,
        backend_id: str | None = None,
        batch_id: UUID | None = None,
        request_id: UUID | None = None,
        correlation_id: str | None = None,
        reason: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        ts = datetime.now(timezone.utc).isoformat()
        fields: dict[str, Any] = {
            "event_type": event_type.value,
            "backend_event": True,
            "timestamp": ts,
        }
        if backend_id is not None:
            fields["backend_id"] = backend_id
        if batch_id is not None:
            fields["batch_id"] = str(batch_id)
        if reason is not None:
            fields["reason"] = reason
        if correlation_id is not None:
            fields["correlation_id"] = correlation_id
        if extra:
            fields.update(extra)

        ctx = LogContext(
            service=self._service_name,
            request_id=request_id,
            trace_id=correlation_id,
        )
        self._logger.info(event_type.value, ctx=ctx, **fields)
        if self._recorder is not None and request_id is not None:
            recorded_at = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            resolved_correlation = correlation_id or ""
            if not resolved_correlation:
                existing = self._recorder.store.get(request_id)
                if existing is not None:
                    resolved_correlation = existing.context.correlation_id
            batch_key = str(batch_id) if batch_id is not None else None
            self._recorder.record_backend(
                BackendEventRecord(
                    request_id=request_id,
                    correlation_id=resolved_correlation,
                    timestamp=recorded_at,
                    component=RuntimeComponent.ADAPTER,
                    event_type=event_type.value,
                    batch_id=batch_key,
                    backend_id=backend_id,
                    decision_reason=reason,
                    extra=extra or {},
                )
            )
            if event_type == BackendEventType.BATCH_REJECTED:
                self._recorder.record_failure(
                    FailureEventRecord(
                        request_id=request_id,
                        correlation_id=resolved_correlation,
                        timestamp=recorded_at,
                        component=RuntimeComponent.ADAPTER,
                        event_type=event_type.value,
                        failure_type="backend_rejected",
                        failure_reason=reason or "batch_rejected",
                        failure_state="failed",
                        batch_id=batch_key,
                        backend_id=backend_id,
                    )
                )
