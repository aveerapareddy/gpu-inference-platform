"""Persistence observability events. Owner: gpu_inference_observability.persistence."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID

from gpu_inference_observability import LogContext, StructuredLogger
from gpu_inference_observability.runtime.models import RuntimeComponent, TraceEvent
from gpu_inference_observability.runtime.recorder import RuntimeEventRecorder


class PersistenceEventType(StrEnum):
    PERSISTENCE_WRITE = "persistence_write"
    PERSISTENCE_READ = "persistence_read"
    PERSISTENCE_FAILURE = "persistence_failure"
    PERSISTENCE_RECOVERY = "persistence_recovery"


class PersistenceEventEmitter:
    def __init__(
        self,
        logger: StructuredLogger,
        service_name: str = "persistence",
        *,
        trace_recorder: RuntimeEventRecorder | None = None,
    ) -> None:
        self._logger = logger
        self._service_name = service_name
        self._recorder = trace_recorder

    def emit(
        self,
        event_type: PersistenceEventType,
        *,
        entity_type: str,
        entity_id: UUID | str,
        request_id: UUID | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        ts = datetime.now(timezone.utc)
        entity_id_str = str(entity_id)
        fields: dict[str, Any] = {
            "event_type": event_type.value,
            "persistence_event": True,
            "entity_type": entity_type,
            "entity_id": entity_id_str,
            "timestamp": ts.isoformat(),
        }
        if extra:
            fields.update(extra)

        ctx = LogContext(
            service=self._service_name,
            request_id=request_id,
            trace_id=entity_id_str if request_id is None else str(request_id),
        )
        self._logger.info(event_type.value, ctx=ctx, **fields)

        if self._recorder is not None and request_id is not None:
            self._recorder.store.append_event(
                TraceEvent(
                    request_id=request_id,
                    correlation_id=str(request_id),
                    timestamp=ts,
                    component=RuntimeComponent.CONTROL_PLANE,
                    event_type=event_type.value,
                    extra={
                        "entity_type": entity_type,
                        "entity_id": entity_id_str,
                        **(extra or {}),
                    },
                )
            )

    def write(self, entity_type: str, entity_id: UUID | str, *, request_id: UUID | None = None) -> None:
        self.emit(
            PersistenceEventType.PERSISTENCE_WRITE,
            entity_type=entity_type,
            entity_id=entity_id,
            request_id=request_id,
        )

    def read(self, entity_type: str, entity_id: UUID | str, *, request_id: UUID | None = None) -> None:
        self.emit(
            PersistenceEventType.PERSISTENCE_READ,
            entity_type=entity_type,
            entity_id=entity_id,
            request_id=request_id,
        )

    def failure(
        self,
        entity_type: str,
        entity_id: UUID | str,
        *,
        error: str,
        request_id: UUID | None = None,
    ) -> None:
        self.emit(
            PersistenceEventType.PERSISTENCE_FAILURE,
            entity_type=entity_type,
            entity_id=entity_id,
            request_id=request_id,
            extra={"error": error},
        )

    def recovery(self, entity_type: str, entity_id: UUID | str, *, count: int) -> None:
        self.emit(
            PersistenceEventType.PERSISTENCE_RECOVERY,
            entity_type=entity_type,
            entity_id=entity_id,
            extra={"recovered_count": count},
        )
