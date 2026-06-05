"""Replay observability events."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID

from gpu_inference_observability import LogContext, StructuredLogger
from gpu_inference_observability.runtime.models import RuntimeComponent, TraceEvent
from gpu_inference_observability.runtime.recorder import RuntimeEventRecorder
from gpu_inference_observability.runtime.store import RequestTraceStore


class ReplayEventType(StrEnum):
    REQUEST_REPLAYED = "request_replayed"
    REPLAY_STARTED = "replay_started"
    REPLAY_COMPLETED = "replay_completed"
    REPLAY_FAILED = "replay_failed"
    COMPARISON_GENERATED = "comparison_generated"


class ReplayEventEmitter:
    """Emits replay events via structured logs and runtime trace store."""

    def __init__(
        self,
        logger: StructuredLogger,
        service_name: str = "replay",
        *,
        trace_recorder: RuntimeEventRecorder | None = None,
    ) -> None:
        self._logger = logger
        self._service_name = service_name
        self._recorder = trace_recorder

    def emit(
        self,
        event_type: ReplayEventType,
        *,
        request_id: UUID,
        replay_id: UUID | None = None,
        source_request_id: UUID | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        ts = datetime.now(timezone.utc)
        fields: dict[str, Any] = {
            "event_type": event_type.value,
            "replay_event": True,
            "timestamp": ts.isoformat(),
        }
        if replay_id is not None:
            fields["replay_id"] = str(replay_id)
        if source_request_id is not None:
            fields["source_request_id"] = str(source_request_id)
        if extra:
            fields.update(extra)

        ctx = LogContext(
            service=self._service_name,
            request_id=request_id,
            trace_id=str(source_request_id) if source_request_id else None,
        )
        self._logger.info(event_type.value, ctx=ctx, **fields)

        if self._recorder is not None:
            self._recorder.store.append_event(
                TraceEvent(
                    request_id=request_id,
                    correlation_id=str(source_request_id or request_id),
                    timestamp=ts,
                    component=RuntimeComponent.REPLAY,
                    event_type=event_type.value,
                    extra={
                        "replay_id": str(replay_id) if replay_id else None,
                        "source_request_id": str(source_request_id) if source_request_id else None,
                        **(extra or {}),
                    },
                )
            )
