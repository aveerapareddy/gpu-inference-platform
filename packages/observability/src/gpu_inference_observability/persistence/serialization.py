"""JSON serialization for persistence. Owner: gpu_inference_observability.persistence."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import UUID

from gpu_inference_observability.runtime.models import FailureRecord, RuntimeComponent, TraceEvent
from gpu_inference_observability.runtime.replay.models import (
    ExecutionComparison,
    ExecutionDifference,
    ExecutionDifferenceKind,
    LifecycleTransitionSnapshot,
    ReplayOutcome,
    RequestExecutionRecord,
    RequestPayloadSnapshot,
    TerminalOutcome,
)
from gpu_inference_observability.persistence.models import (
    BatchDecision,
    LifecycleTransition,
    PersistedFailureRecord,
    ReplayComparisonRecord,
    ReplayExecution,
    RequestMetadata,
    SchedulerDecision,
    SpanMetadata,
    TraceSummary,
    FailureCategory,
)


class PersistenceEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, UUID):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, RuntimeComponent):
            return obj.value
        if isinstance(obj, FailureCategory):
            return obj.value
        if isinstance(obj, ReplayOutcome):
            return obj.value
        if isinstance(obj, ExecutionDifferenceKind):
            return obj.value
        return super().default(obj)


def dumps(data: Any) -> str:
    return json.dumps(data, cls=PersistenceEncoder, sort_keys=True)


def loads(raw: str) -> Any:
    return json.loads(raw)


def trace_event_to_dict(event: TraceEvent) -> dict[str, Any]:
    return {
        "request_id": str(event.request_id),
        "correlation_id": event.correlation_id,
        "timestamp": event.timestamp.isoformat(),
        "component": event.component.value,
        "event_type": event.event_type,
        "batch_id": event.batch_id,
        "backend_id": event.backend_id,
        "lifecycle_state": event.lifecycle_state,
        "decision_reason": event.decision_reason,
        "extra": event.extra,
    }


def trace_event_from_dict(data: dict[str, Any]) -> TraceEvent:
    return TraceEvent(
        request_id=UUID(data["request_id"]),
        correlation_id=data["correlation_id"],
        timestamp=datetime.fromisoformat(data["timestamp"]),
        component=RuntimeComponent(data["component"]),
        event_type=data["event_type"],
        batch_id=data.get("batch_id"),
        backend_id=data.get("backend_id"),
        lifecycle_state=data.get("lifecycle_state"),
        decision_reason=data.get("decision_reason"),
        extra=data.get("extra") or {},
    )


def failure_record_to_dict(record: FailureRecord) -> dict[str, Any]:
    return {
        "failure_type": record.failure_type,
        "failure_owner": record.failure_owner.value,
        "failure_component": record.failure_component,
        "failure_timestamp": record.failure_timestamp.isoformat(),
        "failure_reason": record.failure_reason,
        "failure_state": record.failure_state,
        "request_id": str(record.request_id),
        "correlation_id": record.correlation_id,
        "batch_id": record.batch_id,
        "backend_id": record.backend_id,
    }


def failure_record_from_dict(data: dict[str, Any]) -> FailureRecord:
    return FailureRecord(
        failure_type=data["failure_type"],
        failure_owner=RuntimeComponent(data["failure_owner"]),
        failure_component=data["failure_component"],
        failure_timestamp=datetime.fromisoformat(data["failure_timestamp"]),
        failure_reason=data["failure_reason"],
        failure_state=data["failure_state"],
        request_id=UUID(data["request_id"]),
        correlation_id=data["correlation_id"],
        batch_id=data.get("batch_id"),
        backend_id=data.get("backend_id"),
    )


def lifecycle_snapshot_to_dict(snapshot: LifecycleTransitionSnapshot) -> dict[str, Any]:
    return {
        "event_type": snapshot.event_type,
        "from_state": snapshot.from_state,
        "to_state": snapshot.to_state,
        "timestamp": snapshot.timestamp.isoformat(),
    }


def lifecycle_snapshot_from_dict(data: dict[str, Any]) -> LifecycleTransitionSnapshot:
    return LifecycleTransitionSnapshot(
        event_type=data["event_type"],
        from_state=data.get("from_state"),
        to_state=data.get("to_state"),
        timestamp=datetime.fromisoformat(data["timestamp"]),
    )


def terminal_outcome_to_dict(outcome: TerminalOutcome) -> dict[str, Any]:
    return {
        "state": outcome.state,
        "failure_reason": outcome.failure_reason,
        "failure_message": outcome.failure_message,
        "batch_id": outcome.batch_id,
        "backend_id": outcome.backend_id,
    }


def terminal_outcome_from_dict(data: dict[str, Any]) -> TerminalOutcome:
    return TerminalOutcome(
        state=data["state"],
        failure_reason=data.get("failure_reason"),
        failure_message=data.get("failure_message"),
        batch_id=data.get("batch_id"),
        backend_id=data.get("backend_id"),
    )


def payload_snapshot_to_dict(payload: RequestPayloadSnapshot) -> dict[str, Any]:
    return {
        "inference_request": payload.inference_request,
        "request_context": payload.request_context,
    }


def payload_snapshot_from_dict(data: dict[str, Any]) -> RequestPayloadSnapshot:
    return RequestPayloadSnapshot(
        inference_request=data["inference_request"],
        request_context=data["request_context"],
    )


def execution_record_to_dict(record: RequestExecutionRecord) -> dict[str, Any]:
    return {
        "request_id": str(record.request_id),
        "correlation_id": record.correlation_id,
        "captured_at": record.captured_at.isoformat(),
        "payload": payload_snapshot_to_dict(record.payload),
        "lifecycle_transitions": [lifecycle_snapshot_to_dict(t) for t in record.lifecycle_transitions],
        "queue_events": [trace_event_to_dict(e) for e in record.queue_events],
        "scheduler_events": [trace_event_to_dict(e) for e in record.scheduler_events],
        "batch_events": [trace_event_to_dict(e) for e in record.batch_events],
        "backend_events": [trace_event_to_dict(e) for e in record.backend_events],
        "failures": [failure_record_to_dict(f) for f in record.failures],
        "terminal_outcome": terminal_outcome_to_dict(record.terminal_outcome),
        "event_timeline": [trace_event_to_dict(e) for e in record.event_timeline],
        "replay_id": str(record.replay_id) if record.replay_id else None,
        "source_request_id": str(record.source_request_id) if record.source_request_id else None,
        "completion": _completion_to_dict(record.completion),
    }


def _completion_to_dict(completion: Any) -> dict[str, Any] | None:
    if completion is None:
        return None
    if hasattr(completion, "model_dump"):
        return completion.model_dump()
    return completion


def execution_record_from_dict(data: dict[str, Any]) -> RequestExecutionRecord:
    return RequestExecutionRecord(
        request_id=UUID(data["request_id"]),
        correlation_id=data["correlation_id"],
        captured_at=datetime.fromisoformat(data["captured_at"]),
        payload=payload_snapshot_from_dict(data["payload"]),
        lifecycle_transitions=tuple(
            lifecycle_snapshot_from_dict(item) for item in data["lifecycle_transitions"]
        ),
        queue_events=tuple(trace_event_from_dict(item) for item in data["queue_events"]),
        scheduler_events=tuple(trace_event_from_dict(item) for item in data["scheduler_events"]),
        batch_events=tuple(trace_event_from_dict(item) for item in data["batch_events"]),
        backend_events=tuple(trace_event_from_dict(item) for item in data["backend_events"]),
        failures=tuple(failure_record_from_dict(item) for item in data["failures"]),
        terminal_outcome=terminal_outcome_from_dict(data["terminal_outcome"]),
        event_timeline=tuple(trace_event_from_dict(item) for item in data["event_timeline"]),
        replay_id=UUID(data["replay_id"]) if data.get("replay_id") else None,
        source_request_id=UUID(data["source_request_id"]) if data.get("source_request_id") else None,
        completion=_completion_from_dict(data.get("completion")),
    )


def _completion_from_dict(data: dict[str, Any] | None):
    if not data:
        return None
    from common_schemas.completion import InferenceCompletionRecord

    return InferenceCompletionRecord.model_validate(data)


def request_metadata_to_dict(metadata: RequestMetadata) -> dict[str, Any]:
    return {
        "request_id": str(metadata.request_id),
        "correlation_id": metadata.correlation_id,
        "model": metadata.model,
        "terminal_state": metadata.terminal_state,
        "captured_at": metadata.captured_at.isoformat(),
        "payload": payload_snapshot_to_dict(metadata.payload),
        "terminal_outcome": terminal_outcome_to_dict(metadata.terminal_outcome),
    }


def request_metadata_from_dict(data: dict[str, Any]) -> RequestMetadata:
    return RequestMetadata(
        request_id=UUID(data["request_id"]),
        correlation_id=data["correlation_id"],
        model=data.get("model"),
        terminal_state=data["terminal_state"],
        captured_at=datetime.fromisoformat(data["captured_at"]),
        payload=payload_snapshot_from_dict(data["payload"]),
        terminal_outcome=terminal_outcome_from_dict(data["terminal_outcome"]),
    )


def lifecycle_transition_to_dict(transition: LifecycleTransition) -> dict[str, Any]:
    return {
        "request_id": str(transition.request_id),
        "sequence_num": transition.sequence_num,
        "event_type": transition.event_type,
        "from_state": transition.from_state,
        "to_state": transition.to_state,
        "timestamp": transition.timestamp.isoformat(),
    }


def lifecycle_transition_from_dict(data: dict[str, Any]) -> LifecycleTransition:
    return LifecycleTransition(
        request_id=UUID(data["request_id"]),
        sequence_num=data["sequence_num"],
        event_type=data["event_type"],
        from_state=data.get("from_state"),
        to_state=data.get("to_state"),
        timestamp=datetime.fromisoformat(data["timestamp"]),
    )


def scheduler_decision_to_dict(decision: SchedulerDecision) -> dict[str, Any]:
    return {
        "request_id": str(decision.request_id),
        "sequence_num": decision.sequence_num,
        "event_type": decision.event_type,
        "decision_reason": decision.decision_reason,
        "scheduler_cycle_id": decision.scheduler_cycle_id,
        "batch_id": decision.batch_id,
        "timestamp": decision.timestamp.isoformat(),
        "details": decision.details,
    }


def scheduler_decision_from_dict(data: dict[str, Any]) -> SchedulerDecision:
    return SchedulerDecision(
        request_id=UUID(data["request_id"]),
        sequence_num=data["sequence_num"],
        event_type=data["event_type"],
        decision_reason=data.get("decision_reason"),
        scheduler_cycle_id=data.get("scheduler_cycle_id"),
        batch_id=data.get("batch_id"),
        timestamp=datetime.fromisoformat(data["timestamp"]),
        details=data.get("details") or {},
    )


def batch_decision_to_dict(decision: BatchDecision) -> dict[str, Any]:
    return {
        "request_id": str(decision.request_id),
        "sequence_num": decision.sequence_num,
        "event_type": decision.event_type,
        "batch_id": decision.batch_id,
        "decision_reason": decision.decision_reason,
        "timestamp": decision.timestamp.isoformat(),
        "details": decision.details,
    }


def batch_decision_from_dict(data: dict[str, Any]) -> BatchDecision:
    return BatchDecision(
        request_id=UUID(data["request_id"]),
        sequence_num=data["sequence_num"],
        event_type=data["event_type"],
        batch_id=data.get("batch_id"),
        decision_reason=data.get("decision_reason"),
        timestamp=datetime.fromisoformat(data["timestamp"]),
        details=data.get("details") or {},
    )


def persisted_failure_to_dict(record: PersistedFailureRecord) -> dict[str, Any]:
    return {
        "failure_id": str(record.failure_id),
        "request_id": str(record.request_id),
        "failure_type": record.failure_type,
        "failure_owner": record.failure_owner.value,
        "failure_component": record.failure_component,
        "failure_category": record.failure_category.value,
        "failure_reason": record.failure_reason,
        "failure_state": record.failure_state,
        "failure_timestamp": record.failure_timestamp.isoformat(),
        "correlation_id": record.correlation_id,
        "batch_id": record.batch_id,
        "backend_id": record.backend_id,
    }


def persisted_failure_from_dict(data: dict[str, Any]) -> PersistedFailureRecord:
    return PersistedFailureRecord(
        failure_id=UUID(data["failure_id"]),
        request_id=UUID(data["request_id"]),
        failure_type=data["failure_type"],
        failure_owner=RuntimeComponent(data["failure_owner"]),
        failure_component=data["failure_component"],
        failure_category=FailureCategory(data["failure_category"]),
        failure_reason=data["failure_reason"],
        failure_state=data["failure_state"],
        failure_timestamp=datetime.fromisoformat(data["failure_timestamp"]),
        correlation_id=data["correlation_id"],
        batch_id=data.get("batch_id"),
        backend_id=data.get("backend_id"),
    )


def trace_summary_to_dict(summary: TraceSummary) -> dict[str, Any]:
    return {
        "request_id": str(summary.request_id),
        "correlation_id": summary.correlation_id,
        "event_count": summary.event_count,
        "failure_count": summary.failure_count,
        "stage_durations_ms": summary.stage_durations_ms,
        "span_metadata": [
            {
                "span_name": span.span_name,
                "component": span.component,
                "started_at": span.started_at.isoformat() if span.started_at else None,
                "ended_at": span.ended_at.isoformat() if span.ended_at else None,
                "attributes": span.attributes,
            }
            for span in summary.span_metadata
        ],
        "captured_at": summary.captured_at.isoformat(),
    }


def trace_summary_from_dict(data: dict[str, Any]) -> TraceSummary:
    spans = tuple(
        SpanMetadata(
            span_name=item["span_name"],
            component=item["component"],
            started_at=datetime.fromisoformat(item["started_at"]) if item.get("started_at") else None,
            ended_at=datetime.fromisoformat(item["ended_at"]) if item.get("ended_at") else None,
            attributes=item.get("attributes") or {},
        )
        for item in data["span_metadata"]
    )
    return TraceSummary(
        request_id=UUID(data["request_id"]),
        correlation_id=data["correlation_id"],
        event_count=data["event_count"],
        failure_count=data["failure_count"],
        stage_durations_ms=data["stage_durations_ms"],
        span_metadata=spans,
        captured_at=datetime.fromisoformat(data["captured_at"]),
    )


def replay_execution_to_dict(record: ReplayExecution) -> dict[str, Any]:
    return {
        "replay_id": str(record.replay_id),
        "source_request_id": str(record.source_request_id) if record.source_request_id else None,
        "replay_request_id": str(record.replay_request_id),
        "outcome": record.outcome.value,
        "terminal_state": record.terminal_state,
        "failure_reason": record.failure_reason,
        "failure_message": record.failure_message,
        "started_at": record.started_at.isoformat(),
        "completed_at": record.completed_at.isoformat(),
        "replay_events": list(record.replay_events),
    }


def replay_execution_from_dict(data: dict[str, Any]) -> ReplayExecution:
    return ReplayExecution(
        replay_id=UUID(data["replay_id"]),
        source_request_id=UUID(data["source_request_id"]) if data.get("source_request_id") else None,
        replay_request_id=UUID(data["replay_request_id"]),
        outcome=ReplayOutcome(data["outcome"]),
        terminal_state=data["terminal_state"],
        failure_reason=data.get("failure_reason"),
        failure_message=data.get("failure_message"),
        started_at=datetime.fromisoformat(data["started_at"]),
        completed_at=datetime.fromisoformat(data["completed_at"]),
        replay_events=tuple(data.get("replay_events") or ()),
    )


def replay_comparison_to_dict(record: ReplayComparisonRecord) -> dict[str, Any]:
    return {
        "comparison_id": str(record.comparison_id),
        "original_request_id": str(record.original_request_id),
        "replay_request_id": str(record.replay_request_id),
        "generated_at": record.generated_at.isoformat(),
        "terminal_state_match": record.terminal_state_match,
        "matches": record.matches,
        "differences": list(record.differences),
    }


def replay_comparison_from_dict(data: dict[str, Any]) -> ReplayComparisonRecord:
    return ReplayComparisonRecord(
        comparison_id=UUID(data["comparison_id"]),
        original_request_id=UUID(data["original_request_id"]),
        replay_request_id=UUID(data["replay_request_id"]),
        generated_at=datetime.fromisoformat(data["generated_at"]),
        terminal_state_match=bool(data["terminal_state_match"]),
        matches=bool(data["matches"]),
        differences=tuple(data.get("differences") or ()),
    )


def execution_comparison_to_dict(comparison: ExecutionComparison) -> dict[str, Any]:
    return {
        "original_request_id": str(comparison.original_request_id),
        "replay_request_id": str(comparison.replay_request_id),
        "generated_at": comparison.generated_at.isoformat(),
        "terminal_state_match": comparison.terminal_state_match,
        "matches": comparison.matches,
        "differences": [
            {
                "kind": diff.kind.value,
                "field": diff.field,
                "original": diff.original,
                "replay": diff.replay,
                "detail": diff.detail,
            }
            for diff in comparison.differences
        ],
        "original_terminal_state": comparison.original_terminal_state,
        "replay_terminal_state": comparison.replay_terminal_state,
    }


def execution_comparison_from_dict(data: dict[str, Any]) -> ExecutionComparison:
    differences = tuple(
        ExecutionDifference(
            kind=ExecutionDifferenceKind(item["kind"]),
            field=item["field"],
            original=item.get("original"),
            replay=item.get("replay"),
            detail=item.get("detail"),
        )
        for item in data["differences"]
    )
    return ExecutionComparison(
        original_request_id=UUID(data["original_request_id"]),
        replay_request_id=UUID(data["replay_request_id"]),
        generated_at=datetime.fromisoformat(data["generated_at"]),
        terminal_state_match=bool(data["terminal_state_match"]),
        differences=differences,
        original_terminal_state=data["original_terminal_state"],
        replay_terminal_state=data["replay_terminal_state"],
    )
