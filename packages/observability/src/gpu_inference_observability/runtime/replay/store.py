"""In-memory execution record storage."""

from __future__ import annotations

import threading
from uuid import UUID

from gpu_inference_observability.runtime.replay.models import RequestExecutionRecord


class ExecutionRecordStore:
    def __init__(self) -> None:
        self._records: dict[UUID, RequestExecutionRecord] = {}
        self._lock = threading.RLock()

    def put(self, record: RequestExecutionRecord) -> None:
        with self._lock:
            self._records[record.request_id] = record

    def get(self, request_id: UUID) -> RequestExecutionRecord | None:
        with self._lock:
            return self._records.get(request_id)

    def list_request_ids(self) -> list[UUID]:
        with self._lock:
            return list(self._records.keys())

    def clear(self) -> None:
        with self._lock:
            self._records.clear()
