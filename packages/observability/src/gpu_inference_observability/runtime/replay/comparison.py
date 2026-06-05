"""Compare original and replay executions."""

from __future__ import annotations

from datetime import datetime, timezone

from gpu_inference_observability.runtime.models import RuntimeComponent, TraceEvent
from gpu_inference_observability.runtime.replay.models import (
    ExecutionComparison,
    ExecutionDifference,
    ExecutionDifferenceKind,
    RequestExecutionRecord,
)


def compare_executions(
    original: RequestExecutionRecord,
    replay: RequestExecutionRecord,
) -> ExecutionComparison:
    differences: list[ExecutionDifference] = []

    _compare_terminal(original, replay, differences)
    _compare_lifecycle(original, replay, differences)
    _compare_event_sets(
        ExecutionDifferenceKind.SCHEDULER,
        "scheduler_events",
        original.scheduler_events,
        replay.scheduler_events,
        differences,
    )
    _compare_event_sets(
        ExecutionDifferenceKind.BATCH,
        "batch_events",
        original.batch_events,
        replay.batch_events,
        differences,
    )
    _compare_event_sets(
        ExecutionDifferenceKind.BACKEND,
        "backend_events",
        original.backend_events,
        replay.backend_events,
        differences,
    )
    _compare_event_sequence(original.event_timeline, replay.event_timeline, differences)

    terminal_match = original.terminal_outcome.state == replay.terminal_outcome.state
    return ExecutionComparison(
        original_request_id=original.request_id,
        replay_request_id=replay.request_id,
        generated_at=datetime.now(timezone.utc),
        terminal_state_match=terminal_match,
        differences=tuple(differences),
        original_terminal_state=original.terminal_outcome.state,
        replay_terminal_state=replay.terminal_outcome.state,
    )


def _compare_terminal(
    original: RequestExecutionRecord,
    replay: RequestExecutionRecord,
    differences: list[ExecutionDifference],
) -> None:
    orig = original.terminal_outcome
    repl = replay.terminal_outcome
    if orig.state != repl.state:
        differences.append(
            ExecutionDifference(
                kind=ExecutionDifferenceKind.TERMINAL,
                field="state",
                original=orig.state,
                replay=repl.state,
            )
        )
    if orig.failure_reason != repl.failure_reason:
        differences.append(
            ExecutionDifference(
                kind=ExecutionDifferenceKind.TERMINAL,
                field="failure_reason",
                original=orig.failure_reason,
                replay=repl.failure_reason,
            )
        )
    if orig.backend_id != repl.backend_id:
        differences.append(
            ExecutionDifference(
                kind=ExecutionDifferenceKind.TERMINAL,
                field="backend_id",
                original=orig.backend_id,
                replay=repl.backend_id,
            )
        )


def _compare_lifecycle(
    original: RequestExecutionRecord,
    replay: RequestExecutionRecord,
    differences: list[ExecutionDifference],
) -> None:
    orig_path = tuple(t.to_state or t.event_type for t in original.lifecycle_transitions)
    repl_path = tuple(t.to_state or t.event_type for t in replay.lifecycle_transitions)
    if orig_path != repl_path:
        differences.append(
            ExecutionDifference(
                kind=ExecutionDifferenceKind.LIFECYCLE,
                field="transition_path",
                original=" -> ".join(orig_path) if orig_path else None,
                replay=" -> ".join(repl_path) if repl_path else None,
            )
        )


def _compare_event_sets(
    kind: ExecutionDifferenceKind,
    field: str,
    original: tuple[TraceEvent, ...],
    replay: tuple[TraceEvent, ...],
    differences: list[ExecutionDifference],
) -> None:
    orig_types = [e.event_type for e in original]
    repl_types = [e.event_type for e in replay]
    if orig_types != repl_types:
        differences.append(
            ExecutionDifference(
                kind=kind,
                field=field,
                original=",".join(orig_types) or None,
                replay=",".join(repl_types) or None,
            )
        )


def _compare_event_sequence(
    original: tuple[TraceEvent, ...],
    replay: tuple[TraceEvent, ...],
    differences: list[ExecutionDifference],
) -> None:
    orig_sig = _execution_event_signature(original)
    repl_sig = _execution_event_signature(replay)
    if orig_sig != repl_sig:
        differences.append(
            ExecutionDifference(
                kind=ExecutionDifferenceKind.EVENT_SEQUENCE,
                field="execution_timeline",
                original=",".join(orig_sig) or None,
                replay=",".join(repl_sig) or None,
                detail=f"original={len(orig_sig)} replay={len(repl_sig)}",
            )
        )


_EXECUTION_COMPONENTS = frozenset(
    {
        RuntimeComponent.CONTROL_PLANE,
        RuntimeComponent.SCHEDULER,
        RuntimeComponent.ADAPTER,
        RuntimeComponent.BACKEND,
    }
)


def _execution_event_signature(events: tuple[TraceEvent, ...]) -> tuple[str, ...]:
    """Platform execution events only; excludes gateway ingress and replay metadata."""
    return tuple(
        f"{event.component.value}:{event.event_type}"
        for event in events
        if event.component in _EXECUTION_COMPONENTS
    )
