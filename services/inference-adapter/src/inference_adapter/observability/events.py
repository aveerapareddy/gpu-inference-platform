"""Adapter structured events (logs only)."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID

from gpu_inference_observability import LogContext, StructuredLogger


class BackendEventType(StrEnum):
    BACKEND_REGISTERED = "backend_registered"
    BACKEND_REMOVED = "backend_removed"
    BACKEND_SELECTED = "backend_selected"
    BATCH_SUBMITTED = "batch_submitted"
    BATCH_ACCEPTED = "batch_accepted"
    BATCH_REJECTED = "batch_rejected"
    BACKEND_HEALTH_CHANGED = "backend_health_changed"


class BackendEventEmitter:
    def __init__(self, logger: StructuredLogger, service_name: str) -> None:
        self._logger = logger
        self._service_name = service_name

    def emit(
        self,
        event_type: BackendEventType,
        *,
        backend_id: str | None = None,
        batch_id: UUID | None = None,
        request_id: UUID | None = None,
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
        if extra:
            fields.update(extra)

        ctx = LogContext(
            service=self._service_name,
            request_id=request_id,
        )
        self._logger.info(event_type.value, ctx=ctx, **fields)
