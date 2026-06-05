"""Durable execution record store with in-memory cache."""

from __future__ import annotations

from uuid import UUID

from gpu_inference_observability.runtime.models import TraceTimeline
from gpu_inference_observability.runtime.replay.models import RequestExecutionRecord
from gpu_inference_observability.runtime.replay.store import ExecutionRecordStore
from gpu_inference_observability.persistence.events import PersistenceEventEmitter
from gpu_inference_observability.persistence.repository import RuntimeRepository


class DurableExecutionRecordStore(ExecutionRecordStore):
    """In-memory cache backed by RuntimeRepository."""

    def __init__(
        self,
        repository: RuntimeRepository,
        *,
        events: PersistenceEventEmitter | None = None,
    ) -> None:
        super().__init__()
        self._repository = repository
        self._events = events

    def put(
        self,
        record: RequestExecutionRecord,
        *,
        timeline: TraceTimeline | None = None,
    ) -> None:
        super().put(record)
        self._repository.persist_execution_record(record, timeline=timeline)

    def get(self, request_id: UUID) -> RequestExecutionRecord | None:
        cached = super().get(request_id)
        if cached is not None:
            return cached
        loaded = self._repository.execution_records.get(request_id)
        if loaded is not None:
            super().put(loaded)
        return loaded

    def list_request_ids(self) -> list[UUID]:
        persisted = self._repository.execution_records.list_request_ids()
        cached = super().list_request_ids()
        merged = {str(item): item for item in persisted}
        for item in cached:
            merged[str(item)] = item
        return list(merged.values())

    def recover(self) -> int:
        count = 0
        for request_id in self._repository.execution_records.list_request_ids():
            record = self._repository.execution_records.get(request_id)
            if record is not None:
                super().put(record)
                count += 1
        if self._events is not None and count > 0:
            self._events.recovery("execution_record", "startup", count=count)
        return count
