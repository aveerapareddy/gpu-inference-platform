"""Reconstruct request execution history for debugging."""

from __future__ import annotations

from uuid import UUID

from gpu_inference_observability.runtime.inspection import TraceInspector
from gpu_inference_observability.runtime.replay.models import ReconstructedExecution, TerminalOutcome
from gpu_inference_observability.runtime.replay.store import ExecutionRecordStore


def reconstruct_request(
    request_id: UUID,
    *,
    execution_store: ExecutionRecordStore | None = None,
    inspector: TraceInspector | None = None,
) -> ReconstructedExecution | None:
    if execution_store is not None:
        record = execution_store.get(request_id)
        if record is not None:
            return ReconstructedExecution(
                request_id=record.request_id,
                correlation_id=record.correlation_id,
                payload=record.payload,
                lifecycle_history=record.lifecycle_transitions,
                scheduler_decisions=record.scheduler_events,
                batch_history=record.batch_events,
                backend_interactions=record.backend_events,
                queue_events=record.queue_events,
                failures=record.failures,
                terminal_outcome=record.terminal_outcome,
                event_timeline=record.event_timeline,
                captured_at=record.captured_at,
            )

    if inspector is None:
        return None

    trace = inspector.get_request_trace(request_id)
    if trace is None:
        return None

    timeline = inspector.get_request_timeline(request_id)
    events = tuple(timeline.events) if timeline else tuple(trace.events)
    failures = tuple(inspector.get_request_failures(request_id))

    from gpu_inference_observability.runtime.replay.capture import (
        QUEUE_EVENT_TYPES,
        SCHEDULER_EVENT_TYPES,
        BATCH_EVENT_TYPES,
        BACKEND_EVENT_TYPES,
        extract_lifecycle_transitions,
        filter_events_by_type,
    )

    terminal = _infer_terminal_outcome(events, failures)
    return ReconstructedExecution(
        request_id=request_id,
        correlation_id=trace.context.correlation_id,
        payload=_empty_payload(request_id, trace.context.correlation_id),
        lifecycle_history=extract_lifecycle_transitions(events),
        scheduler_decisions=filter_events_by_type(events, SCHEDULER_EVENT_TYPES),
        batch_history=filter_events_by_type(events, BATCH_EVENT_TYPES),
        backend_interactions=filter_events_by_type(events, BACKEND_EVENT_TYPES),
        queue_events=filter_events_by_type(events, QUEUE_EVENT_TYPES),
        failures=failures,
        terminal_outcome=terminal,
        event_timeline=events,
        captured_at=None,
    )


def _infer_terminal_outcome(events, failures):
    terminal_state = None
    failure_reason = None
    failure_message = None
    batch_id = None
    backend_id = None
    for event in reversed(events):
        if event.lifecycle_state in {"completed", "failed", "rejected", "timed_out"}:
            terminal_state = event.lifecycle_state
            batch_id = event.batch_id
            backend_id = event.backend_id
            break
    if failures:
        failure_reason = failures[-1].failure_type
        failure_message = failures[-1].failure_reason
    if terminal_state is None:
        return None
    return TerminalOutcome(
        state=terminal_state,
        failure_reason=failure_reason,
        failure_message=failure_message,
        batch_id=batch_id,
        backend_id=backend_id,
    )


def _empty_payload(request_id: UUID, correlation_id: str):
    from gpu_inference_observability.runtime.replay.models import RequestPayloadSnapshot

    return RequestPayloadSnapshot(
        inference_request={"request_id": str(request_id)},
        request_context={"request_id": str(request_id), "trace_id": correlation_id},
    )
