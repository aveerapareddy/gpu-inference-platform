"""Runtime trace inspection interfaces."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from gpu_inference_observability.runtime.models import (
    BackendMetrics,
    BatchMetrics,
    FailureRecord,
    QueueMetrics,
    RequestMetrics,
    RequestTrace,
    SchedulerMetrics,
    TraceTimeline,
)
from gpu_inference_observability.runtime.store import RequestTraceStore


class TraceInspector:
    def __init__(self, store: RequestTraceStore) -> None:
        self._store = store

    def get_request_trace(self, request_id: UUID) -> RequestTrace | None:
        return self._store.get(request_id)

    def get_request_timeline(self, request_id: UUID) -> TraceTimeline | None:
        trace = self._store.get(request_id)
        if trace is None:
            return None
        events = tuple(sorted(trace.events, key=lambda e: e.timestamp))
        return TraceTimeline(
            request_id=trace.context.request_id,
            correlation_id=trace.context.correlation_id,
            events=events,
            stage_durations_ms=trace.timestamps.durations_ms(),
            captured_at=datetime.now(timezone.utc),
        )

    def get_request_metrics(self, request_id: UUID) -> RequestMetrics | None:
        trace = self._store.get(request_id)
        if trace is None:
            return None
        durations = trace.timestamps.durations_ms()
        return RequestMetrics(
            request_id=trace.context.request_id,
            correlation_id=trace.context.correlation_id,
            validation_ms=durations.get("validation_ms"),
            queue_wait_ms=durations.get("queue_wait_ms"),
            schedule_ms=durations.get("schedule_ms"),
            batch_ms=durations.get("batch_ms"),
            submit_ms=durations.get("submit_ms"),
            completion_ms=durations.get("completion_ms"),
            e2e_ms=durations.get("e2e_ms"),
            event_count=len(trace.events),
            failure_count=len(trace.failures),
        )

    def get_queue_metrics(self, request_id: UUID) -> QueueMetrics | None:
        trace = self._store.get(request_id)
        if trace is None:
            return None
        queue_events = [e for e in trace.events if e.component.value == "control_plane" and "queue" in e.event_type]
        position = None
        for event in reversed(trace.events):
            if "queue_position" in event.extra:
                position = event.extra.get("queue_position")
                break
        return QueueMetrics(
            request_id=request_id,
            queue_event_count=len(queue_events),
            last_queue_position=position,
        )

    def get_scheduler_metrics(self, request_id: UUID) -> SchedulerMetrics | None:
        trace = self._store.get(request_id)
        if trace is None:
            return None
        scheduler_events = [e for e in trace.events if e.component.value == "scheduler"]
        selected = any(e.event_type == "request_selected" for e in scheduler_events)
        return SchedulerMetrics(
            request_id=request_id,
            scheduler_event_count=len(scheduler_events),
            selected=selected,
        )

    def get_batch_metrics(self, request_id: UUID) -> BatchMetrics | None:
        trace = self._store.get(request_id)
        if trace is None:
            return None
        batch_events = [
            e
            for e in trace.events
            if "batch" in e.event_type or e.event_type == "request_added_to_batch"
        ]
        return BatchMetrics(
            request_id=request_id,
            batch_id=trace.context.batch_id,
            batch_event_count=len(batch_events),
        )

    def get_backend_metrics(self, request_id: UUID) -> BackendMetrics | None:
        trace = self._store.get(request_id)
        if trace is None:
            return None
        backend_events = [
            e for e in trace.events if e.component.value in {"adapter", "backend"}
        ]
        accepted = any(e.event_type == "batch_accepted" for e in backend_events)
        return BackendMetrics(
            request_id=request_id,
            backend_id=trace.context.backend_id,
            batch_id=trace.context.batch_id,
            backend_event_count=len(backend_events),
            accepted=accepted if backend_events else None,
        )

    def get_request_failures(self, request_id: UUID) -> list[FailureRecord]:
        trace = self._store.get(request_id)
        if trace is None:
            return []
        return list(trace.failures)
