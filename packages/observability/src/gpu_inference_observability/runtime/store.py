"""In-memory request trace storage."""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from uuid import UUID

from gpu_inference_observability.runtime.models import (
    FailureRecord,
    RequestTrace,
    TraceContext,
    TraceEvent,
)


class RequestTraceStore:
    def __init__(self) -> None:
        self._traces: dict[UUID, RequestTrace] = {}
        self._lock = threading.RLock()

    def ensure(self, request_id: UUID, correlation_id: str) -> RequestTrace:
        with self._lock:
            trace = self._traces.get(request_id)
            if trace is None:
                trace = RequestTrace(
                    context=TraceContext(
                        request_id=request_id,
                        correlation_id=correlation_id,
                    )
                )
                self._traces[request_id] = trace
            elif trace.context.correlation_id != correlation_id and correlation_id:
                trace.context = TraceContext(
                    request_id=request_id,
                    correlation_id=correlation_id,
                    batch_id=trace.context.batch_id,
                    backend_id=trace.context.backend_id,
                )
            return trace

    def get(self, request_id: UUID) -> RequestTrace | None:
        with self._lock:
            return self._traces.get(request_id)

    def append_event(self, event: TraceEvent) -> None:
        with self._lock:
            trace = self._traces.get(event.request_id)
            if trace is None:
                trace = self.ensure(event.request_id, event.correlation_id)
            trace.events.append(event)
            if event.batch_id is not None:
                trace.context = TraceContext(
                    request_id=event.request_id,
                    correlation_id=trace.context.correlation_id,
                    batch_id=event.batch_id,
                    backend_id=trace.context.backend_id,
                )
            if event.backend_id is not None:
                trace.context = TraceContext(
                    request_id=event.request_id,
                    correlation_id=trace.context.correlation_id,
                    batch_id=trace.context.batch_id,
                    backend_id=event.backend_id,
                )
            if event.lifecycle_state is not None:
                trace.timestamps.record_lifecycle_state(event.lifecycle_state, event.timestamp)

    def append_failure(self, failure: FailureRecord) -> None:
        with self._lock:
            trace = self.ensure(failure.request_id, failure.correlation_id)
            trace.failures.append(failure)
            if failure.batch_id is not None:
                trace.context = TraceContext(
                    request_id=failure.request_id,
                    correlation_id=trace.context.correlation_id,
                    batch_id=failure.batch_id,
                    backend_id=trace.context.backend_id,
                )
            if failure.backend_id is not None:
                trace.context = TraceContext(
                    request_id=failure.request_id,
                    correlation_id=trace.context.correlation_id,
                    batch_id=trace.context.batch_id,
                    backend_id=failure.backend_id,
                )

    def update_context(
        self,
        request_id: UUID,
        *,
        correlation_id: str | None = None,
        batch_id: str | None = None,
        backend_id: str | None = None,
    ) -> None:
        with self._lock:
            trace = self._traces.get(request_id)
            if trace is None:
                if correlation_id is None:
                    return
                trace = self.ensure(request_id, correlation_id)
            trace.context = TraceContext(
                request_id=request_id,
                correlation_id=correlation_id or trace.context.correlation_id,
                batch_id=batch_id if batch_id is not None else trace.context.batch_id,
                backend_id=backend_id if backend_id is not None else trace.context.backend_id,
            )

    def list_request_ids(self) -> list[UUID]:
        with self._lock:
            return list(self._traces.keys())
