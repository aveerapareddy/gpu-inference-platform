"""GPU capacity observability events."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID

PLATFORM_GPU_EVENT_ID = UUID("00000000-0000-4000-8000-000000000021")

from gpu_inference_observability import LogContext, StructuredLogger
from gpu_inference_observability.runtime.models import RuntimeComponent, TraceEvent
from gpu_inference_observability.runtime.recorder import RuntimeEventRecorder


class CapacityEventType(StrEnum):
    GPU_CAPACITY_WARNING = "gpu_capacity_warning"
    KV_CACHE_PRESSURE_DETECTED = "kv_cache_pressure_detected"
    MEMORY_THRESHOLD_CROSSED = "memory_threshold_crossed"
    CAPACITY_EXHAUSTED = "capacity_exhausted"


class CapacityEventEmitter:
    def __init__(
        self,
        logger: StructuredLogger,
        service_name: str = "gpu_observability",
        *,
        trace_recorder: RuntimeEventRecorder | None = None,
    ) -> None:
        self._logger = logger
        self._service_name = service_name
        self._recorder = trace_recorder

    def emit(
        self,
        event_type: CapacityEventType,
        *,
        extra: dict[str, Any] | None = None,
        request_id: UUID | None = None,
    ) -> None:
        ts = datetime.now(timezone.utc)
        rid = request_id or PLATFORM_GPU_EVENT_ID
        fields: dict[str, Any] = {
            "event_type": event_type.value,
            "capacity_event": True,
            "timestamp": ts.isoformat(),
        }
        if extra:
            fields.update(extra)
        ctx = LogContext(service=self._service_name, request_id=rid, trace_id=str(rid))
        self._logger.warning(event_type.value, ctx=ctx, **fields)
        if self._recorder is not None:
            self._recorder.store.append_event(
                TraceEvent(
                    request_id=rid,
                    correlation_id="gpu_observability",
                    timestamp=ts,
                    component=RuntimeComponent.ADAPTER,
                    event_type=event_type.value,
                    extra={"capacity_event": True, **(extra or {})},
                )
            )
