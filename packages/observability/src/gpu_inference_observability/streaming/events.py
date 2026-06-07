"""Streaming observability events."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID

from gpu_inference_observability import LogContext, StructuredLogger
from gpu_inference_observability.runtime.models import RuntimeComponent, TraceEvent
from gpu_inference_observability.runtime.recorder import RuntimeEventRecorder


class StreamEventType(StrEnum):
    STREAM_CREATED = "stream_created"
    FIRST_TOKEN_EMITTED = "first_token_emitted"
    TOKEN_EMITTED = "token_emitted"
    STREAM_COMPLETED = "stream_completed"
    STREAM_FAILED = "stream_failed"
    STREAM_CANCELLED = "stream_cancelled"


class StreamEventEmitter:
    def __init__(
        self,
        logger: StructuredLogger,
        service_name: str = "streaming",
        *,
        trace_recorder: RuntimeEventRecorder | None = None,
    ) -> None:
        self._logger = logger
        self._service_name = service_name
        self._recorder = trace_recorder

    def emit(
        self,
        event_type: StreamEventType,
        *,
        request_id: UUID,
        stream_id: UUID,
        extra: dict[str, Any] | None = None,
    ) -> None:
        ts = datetime.now(timezone.utc)
        fields: dict[str, Any] = {
            "event_type": event_type.value,
            "stream_event": True,
            "stream_id": str(stream_id),
            "timestamp": ts.isoformat(),
        }
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
                    component=RuntimeComponent.GATEWAY,
                    event_type=event_type.value,
                    extra={"stream_id": str(stream_id), "stream_event": True, **(extra or {})},
                )
            )
