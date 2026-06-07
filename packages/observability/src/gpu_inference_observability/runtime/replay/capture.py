"""Build RequestExecutionRecord from runtime trace and terminal entry."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from gpu_inference_observability.runtime.inspection import TraceInspector
from gpu_inference_observability.runtime.models import RuntimeComponent, TraceEvent
from gpu_inference_observability.runtime.replay.models import (
    LifecycleTransitionSnapshot,
    RequestExecutionRecord,
    RequestPayloadSnapshot,
    TerminalOutcome,
)

_LIFECYCLE_EVENT_TYPES = frozenset(
    {
        "request_received",
        "request_validated",
        "request_admitted",
        "request_queued",
        "request_scheduled",
        "request_batched",
        "request_submitted",
        "request_completed",
        "request_failed",
        "request_rejected",
    }
)

QUEUE_EVENT_TYPES = frozenset(
    {
        "request_enqueued",
        "request_dequeued",
        "queue_full",
        "queue_timeout",
        "queue_removed",
    }
)

SCHEDULER_EVENT_TYPES = frozenset(
    {
        "request_selected",
        "request_skipped",
        "scheduler_cycle_started",
        "scheduler_cycle_completed",
        "scheduler_failure",
    }
)

BATCH_EVENT_TYPES = frozenset(
    {
        "batch_created",
        "batch_admission",
        "batch_full",
        "request_added_to_batch",
        "request_removed_from_batch",
        "batch_completed",
        "batch_failed",
    }
)

BACKEND_EVENT_TYPES = frozenset(
    {
        "batch_submitted",
        "batch_accepted",
        "batch_rejected",
        "backend_selected",
        "backend_registered",
    }
)


def extract_lifecycle_transitions(
    events: tuple[TraceEvent, ...],
) -> tuple[LifecycleTransitionSnapshot, ...]:
    return _extract_lifecycle_transitions(events)


def filter_events_by_type(
    events: tuple[TraceEvent, ...],
    allowed: frozenset[str],
) -> tuple[TraceEvent, ...]:
    return _filter_events(events, allowed)


def capture_execution_record(
    *,
    submit: Any,
    terminal_state: str,
    failure_reason: str | None,
    failure_message: str | None,
    batch_id: UUID | str | None,
    backend_id: str | None,
    inspector: TraceInspector,
    source_request_id: UUID | None = None,
    replay_id: UUID | None = None,
    completion: Any | None = None,
) -> RequestExecutionRecord:
    request_id = submit.inference_request.request_id
    correlation_id = submit.request_context.trace_id
    trace = inspector.get_request_trace(request_id)
    timeline = inspector.get_request_timeline(request_id)
    failures = tuple(inspector.get_request_failures(request_id))

    events = tuple(timeline.events) if timeline else ()
    if not events and trace is not None:
        events = tuple(sorted(trace.events, key=lambda e: e.timestamp))

    lifecycle = _extract_lifecycle_transitions(events)
    return RequestExecutionRecord(
        request_id=request_id,
        correlation_id=correlation_id,
        captured_at=datetime.now(timezone.utc),
        payload=RequestPayloadSnapshot.from_submit(submit),
        lifecycle_transitions=lifecycle,
        queue_events=_filter_events(events, QUEUE_EVENT_TYPES),
        scheduler_events=_filter_events(events, SCHEDULER_EVENT_TYPES),
        batch_events=_filter_events(events, BATCH_EVENT_TYPES),
        backend_events=_filter_events(events, BACKEND_EVENT_TYPES),
        failures=failures,
        terminal_outcome=TerminalOutcome(
            state=terminal_state,
            failure_reason=failure_reason,
            failure_message=failure_message,
            batch_id=str(batch_id) if batch_id is not None else None,
            backend_id=backend_id,
        ),
        event_timeline=events,
        replay_id=replay_id,
        source_request_id=source_request_id or request_id,
        completion=completion,
    )


def _extract_lifecycle_transitions(
    events: tuple[TraceEvent, ...],
) -> tuple[LifecycleTransitionSnapshot, ...]:
    transitions: list[LifecycleTransitionSnapshot] = []
    for event in events:
        if event.event_type not in _LIFECYCLE_EVENT_TYPES:
            continue
        extra = event.extra or {}
        transitions.append(
            LifecycleTransitionSnapshot(
                event_type=event.event_type,
                from_state=extra.get("from_state"),
                to_state=extra.get("to_state") or event.lifecycle_state,
                timestamp=event.timestamp,
            )
        )
    return tuple(transitions)


def _filter_events(
    events: tuple[TraceEvent, ...],
    allowed: frozenset[str],
) -> tuple[TraceEvent, ...]:
    return tuple(e for e in events if e.event_type in allowed)
