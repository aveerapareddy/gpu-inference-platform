"""Replay engine. Reuses runtime execution path via injected execute callback."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable
from uuid import UUID, uuid4

from gpu_inference_observability.runtime.inspection import TraceInspector
from gpu_inference_observability.runtime.replay.capture import capture_execution_record
from gpu_inference_observability.runtime.replay.comparison import compare_executions
from gpu_inference_observability.runtime.replay.events import ReplayEventEmitter, ReplayEventType
from gpu_inference_observability.runtime.replay.models import (
    ExecutionComparison,
    ReplayOutcome,
    ReplayRequest,
    ReplayResult,
    RequestExecutionRecord,
    RequestPayloadSnapshot,
    replay_outcome_from_state,
)
from gpu_inference_observability.runtime.replay.store import ExecutionRecordStore


ExecuteFn = Callable[[Any], Awaitable[Any]]


@dataclass
class ExecutionTerminal:
    submit: Any
    state: str
    failure_reason: str | None = None
    failure_message: str | None = None
    batch_id: Any = None
    backend_id: str | None = None


class ReplayEngine:
    """Capture, replay, and compare request executions."""

    def __init__(
        self,
        *,
        execution_store: ExecutionRecordStore,
        inspector: TraceInspector,
        replay_events: ReplayEventEmitter,
        submit_builder: Callable[[RequestPayloadSnapshot], Any] | None = None,
    ) -> None:
        self._store = execution_store
        self._inspector = inspector
        self._events = replay_events
        self._submit_builder = submit_builder

    @property
    def execution_store(self) -> ExecutionRecordStore:
        return self._store

    @property
    def inspector(self) -> TraceInspector:
        return self._inspector

    def capture_execution(
        self,
        terminal: ExecutionTerminal,
        *,
        source_request_id: UUID | None = None,
        replay_id: UUID | None = None,
    ) -> RequestExecutionRecord:
        record = capture_execution_record(
            submit=terminal.submit,
            terminal_state=terminal.state,
            failure_reason=terminal.failure_reason,
            failure_message=terminal.failure_message,
            batch_id=terminal.batch_id,
            backend_id=terminal.backend_id,
            inspector=self._inspector,
            source_request_id=source_request_id,
            replay_id=replay_id,
        )
        self._store.put(record)
        return record

    def capture_from_entry(self, entry: Any) -> RequestExecutionRecord:
        failure_reason = entry.failure_reason.value if entry.failure_reason else None
        return self.capture_execution(
            ExecutionTerminal(
                submit=entry.submit,
                state=entry.state.value,
                failure_reason=failure_reason,
                failure_message=entry.failure_message,
                batch_id=entry.batch_id,
                backend_id=entry.backend_id,
            )
        )

    async def replay(
        self,
        request: ReplayRequest,
        execute: ExecuteFn,
    ) -> ReplayResult:
        replay_id = request.replay_id
        source_id = request.source_request_id
        payload = clone_payload_for_replay(request.payload, replay_id)
        events: list[str] = []

        self._events.emit(
            ReplayEventType.REPLAY_STARTED,
            request_id=replay_id,
            replay_id=replay_id,
            source_request_id=source_id,
        )
        events.append(ReplayEventType.REPLAY_STARTED.value)

        try:
            submit = self._build_submit(payload)
            entry = await execute(submit)
            record = self.capture_execution(
                ExecutionTerminal(
                    submit=entry.submit,
                    state=entry.state.value,
                    failure_reason=entry.failure_reason.value if entry.failure_reason else None,
                    failure_message=entry.failure_message,
                    batch_id=entry.batch_id,
                    backend_id=entry.backend_id,
                ),
                source_request_id=source_id,
                replay_id=replay_id,
            )

            outcome = replay_outcome_from_state(entry.state.value)
            event_type = (
                ReplayEventType.REPLAY_COMPLETED
                if outcome == ReplayOutcome.COMPLETED
                else ReplayEventType.REPLAY_FAILED
            )

            self._events.emit(
                event_type,
                request_id=entry.request_id,
                replay_id=replay_id,
                source_request_id=source_id,
                extra={"terminal_state": entry.state.value},
            )
            events.append(event_type.value)

            if source_id is not None:
                self._events.emit(
                    ReplayEventType.REQUEST_REPLAYED,
                    request_id=source_id,
                    replay_id=replay_id,
                    source_request_id=source_id,
                    extra={"replay_request_id": str(entry.request_id)},
                )
                events.append(ReplayEventType.REQUEST_REPLAYED.value)

            return ReplayResult(
                replay_id=replay_id,
                source_request_id=source_id,
                replay_request_id=entry.request_id,
                outcome=outcome,
                terminal_state=entry.state.value,
                failure_reason=entry.failure_reason.value if entry.failure_reason else None,
                failure_message=entry.failure_message,
                execution_record=record,
                replay_events=tuple(events),
            )
        except Exception as exc:
            self._events.emit(
                ReplayEventType.REPLAY_FAILED,
                request_id=replay_id,
                replay_id=replay_id,
                source_request_id=source_id,
                extra={"error": str(exc)},
            )
            return ReplayResult(
                replay_id=replay_id,
                source_request_id=source_id,
                replay_request_id=replay_id,
                outcome=ReplayOutcome.ERROR,
                terminal_state="error",
                failure_reason="replay_error",
                failure_message=str(exc),
                execution_record=None,
                replay_events=tuple(events + [ReplayEventType.REPLAY_FAILED.value]),
                error=str(exc),
            )

    def compare(
        self,
        original: RequestExecutionRecord,
        replay: RequestExecutionRecord,
    ) -> ExecutionComparison:
        comparison = compare_executions(original, replay)
        self._events.emit(
            ReplayEventType.COMPARISON_GENERATED,
            request_id=original.request_id,
            replay_id=replay.replay_id,
            source_request_id=original.request_id,
            extra={
                "replay_request_id": str(replay.request_id),
                "difference_count": len(comparison.differences),
                "matches": comparison.matches,
            },
        )
        return comparison

    def replay_request_from_record(
        self,
        record: RequestExecutionRecord,
        *,
        replay_id: UUID | None = None,
    ) -> ReplayRequest:
        return ReplayRequest(
            replay_id=replay_id or uuid4(),
            payload=record.payload,
            source_request_id=record.request_id,
            source_record=record,
        )

    def _build_submit(self, payload: RequestPayloadSnapshot) -> Any:
        if self._submit_builder is None:
            raise RuntimeError("submit_builder is required for replay execution")
        return self._submit_builder(payload)


def clone_payload_for_replay(
    payload: RequestPayloadSnapshot,
    replay_id: UUID,
) -> RequestPayloadSnapshot:
    inference_request = dict(payload.inference_request)
    request_context = dict(payload.request_context)
    inference_request["request_id"] = replay_id
    request_context["request_id"] = replay_id
    request_context["trace_id"] = f"replay-{replay_id}"
    request_context["span_id"] = f"replay-span-{replay_id}"
    return RequestPayloadSnapshot(
        inference_request=inference_request,
        request_context=request_context,
    )
