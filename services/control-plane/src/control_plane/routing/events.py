"""Routing observability events."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID

from gpu_inference_observability import LogContext, StructuredLogger
from gpu_inference_observability.runtime.models import RuntimeComponent, TraceEvent
from gpu_inference_observability.runtime.recorder import RuntimeEventRecorder


class RoutingEventType(StrEnum):
    ROUTING_STARTED = "routing_started"
    ROUTING_COMPLETED = "routing_completed"
    MODEL_SELECTED = "model_selected"
    BACKEND_SELECTED = "backend_selected"
    FALLBACK_INVOKED = "fallback_invoked"
    ROUTING_FAILED = "routing_failed"


class RoutingEventEmitter:
    def __init__(
        self,
        logger: StructuredLogger,
        service_name: str = "routing",
        *,
        trace_recorder: RuntimeEventRecorder | None = None,
    ) -> None:
        self._logger = logger
        self._service_name = service_name
        self._recorder = trace_recorder

    def emit(
        self,
        event_type: RoutingEventType,
        *,
        request_id: UUID,
        route_id: UUID | None = None,
        model_id: str | None = None,
        backend_id: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        ts = datetime.now(timezone.utc)
        fields: dict[str, Any] = {
            "event_type": event_type.value,
            "routing_event": True,
            "timestamp": ts.isoformat(),
        }
        if route_id is not None:
            fields["route_id"] = str(route_id)
        if model_id is not None:
            fields["model_id"] = model_id
        if backend_id is not None:
            fields["backend_id"] = backend_id
        if extra:
            fields.update(extra)
        ctx = LogContext(
            service=self._service_name,
            request_id=request_id,
            trace_id=str(request_id),
        )
        self._logger.info(event_type.value, ctx=ctx, **fields)
        if self._recorder is not None:
            self._recorder.store.append_event(
                TraceEvent(
                    request_id=request_id,
                    correlation_id=str(request_id),
                    timestamp=ts,
                    component=RuntimeComponent.SCHEDULER,
                    event_type=event_type.value,
                    extra={
                        "routing_event": True,
                        "route_id": str(route_id) if route_id else None,
                        "model_id": model_id,
                        "backend_id": backend_id,
                        **(extra or {}),
                    },
                )
            )
