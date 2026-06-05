"""SQLite runtime persistence backend."""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from uuid import UUID, uuid4

from gpu_inference_observability.runtime.models import RuntimeComponent, TraceTimeline
from gpu_inference_observability.runtime.replay.models import ExecutionComparison, ReplayResult, RequestExecutionRecord
from gpu_inference_observability.persistence.events import PersistenceEventEmitter
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
    batch_decision_from_event,
    lifecycle_transition_from_snapshot,
    persisted_failure_from_runtime,
    replay_comparison_from_execution,
    replay_execution_from_result,
    request_metadata_from_record,
    scheduler_decision_from_event,
)
from gpu_inference_observability.persistence.repository import RuntimeRepository
from gpu_inference_observability.persistence.serialization import (
    batch_decision_from_dict,
    dumps,
    execution_record_from_dict,
    execution_record_to_dict,
    lifecycle_transition_from_dict,
    loads,
    payload_snapshot_from_dict,
    payload_snapshot_to_dict,
    persisted_failure_from_dict,
    replay_comparison_from_dict,
    replay_execution_from_dict,
    scheduler_decision_from_dict,
    terminal_outcome_from_dict,
    terminal_outcome_to_dict,
    trace_summary_from_dict,
    trace_summary_to_dict,
)
from gpu_inference_observability.persistence.sqlite.connection import SqliteConnection


def trace_summary_from_timeline(timeline: TraceTimeline, *, failure_count: int) -> TraceSummary:
    span_metadata = tuple(
        SpanMetadata(
            span_name=f"{event.component.value}:{event.event_type}",
            component=event.component.value,
            started_at=event.timestamp,
            ended_at=event.timestamp,
            attributes={
                "batch_id": event.batch_id,
                "backend_id": event.backend_id,
                "lifecycle_state": event.lifecycle_state,
            },
        )
        for event in timeline.events
    )
    return TraceSummary(
        request_id=timeline.request_id,
        correlation_id=timeline.correlation_id,
        event_count=len(timeline.events),
        failure_count=failure_count,
        stage_durations_ms=timeline.stage_durations_ms,
        span_metadata=span_metadata,
        captured_at=timeline.captured_at,
    )


class SqliteRuntimeRepository(RuntimeRepository):
    def __init__(
        self,
        db_path: str,
        *,
        events: PersistenceEventEmitter | None = None,
    ) -> None:
        self._db = SqliteConnection(db_path)
        self._events = events
        self._lock = threading.RLock()

    @property
    def execution_records(self) -> SqliteExecutionRecordRepository:
        return SqliteExecutionRecordRepository(self._db, self._events, self._lock)

    @property
    def requests(self) -> SqliteRequestRepository:
        return SqliteRequestRepository(self._db, self._events, self._lock)

    @property
    def lifecycle(self) -> SqliteLifecycleRepository:
        return SqliteLifecycleRepository(self._db, self._events, self._lock)

    @property
    def replays(self) -> SqliteReplayRepository:
        return SqliteReplayRepository(self._db, self._events, self._lock)

    @property
    def failures(self) -> SqliteFailureRepository:
        return SqliteFailureRepository(self._db, self._events, self._lock)

    @property
    def traces(self) -> SqliteTraceRepository:
        return SqliteTraceRepository(self._db, self._events, self._lock)

    @property
    def scheduler_decisions(self) -> SqliteSchedulerDecisionRepository:
        return SqliteSchedulerDecisionRepository(self._db, self._events, self._lock)

    @property
    def batch_decisions(self) -> SqliteBatchDecisionRepository:
        return SqliteBatchDecisionRepository(self._db, self._events, self._lock)

    def persist_execution_record(
        self,
        record: RequestExecutionRecord,
        *,
        timeline: TraceTimeline | None = None,
    ) -> None:
        with self._lock:
            conn = self._db.connection
            try:
                metadata = request_metadata_from_record(record)
                self.requests.save_request(metadata)
                transitions = tuple(
                    lifecycle_transition_from_snapshot(record.request_id, index, snapshot)
                    for index, snapshot in enumerate(record.lifecycle_transitions)
                )
                self.lifecycle.save_transitions(record.request_id, transitions)
                scheduler = tuple(
                    scheduler_decision_from_event(record.request_id, index, event)
                    for index, event in enumerate(record.scheduler_events)
                )
                self.scheduler_decisions.save_decisions(scheduler)
                batch = tuple(
                    batch_decision_from_event(record.request_id, index, event)
                    for index, event in enumerate(record.batch_events)
                )
                self.batch_decisions.save_decisions(batch)
                failures = tuple(persisted_failure_from_runtime(failure) for failure in record.failures)
                self.failures.save_failures(failures)
                self.execution_records.save(record)
                if timeline is not None:
                    summary = trace_summary_from_timeline(timeline, failure_count=len(record.failures))
                    self.traces.save_summary(summary)
                conn.commit()
            except Exception as exc:
                conn.rollback()
                if self._events is not None:
                    self._events.failure("execution_record", record.request_id, error=str(exc), request_id=record.request_id)
                raise

    def persist_replay_result(
        self,
        result: ReplayResult,
        *,
        started_at: datetime,
        completed_at: datetime,
        comparison: ExecutionComparison | None = None,
    ) -> None:
        replay = replay_execution_from_result(result, started_at=started_at, completed_at=completed_at)
        self.replays.save_replay(replay)
        if comparison is not None:
            comparison_record = replay_comparison_from_execution(comparison, uuid4())
            self.replays.save_comparison(comparison_record)
        self.commit()

    def close(self) -> None:
        self._db.close()

    def commit(self) -> None:
        with self._lock:
            self._db.connection.commit()


class _SqliteRepoBase:
    def __init__(
        self,
        db: SqliteConnection,
        events: PersistenceEventEmitter | None,
        lock: threading.RLock,
    ) -> None:
        self._db = db
        self._events = events
        self._lock = lock


class SqliteExecutionRecordRepository(_SqliteRepoBase):
    def save(self, record: RequestExecutionRecord) -> None:
        with self._lock:
            self._db.connection.execute(
                """
                INSERT OR REPLACE INTO execution_records
                (request_id, record_json, captured_at, source_request_id, replay_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    str(record.request_id),
                    dumps(execution_record_to_dict(record)),
                    record.captured_at.isoformat(),
                    str(record.source_request_id) if record.source_request_id else None,
                    str(record.replay_id) if record.replay_id else None,
                ),
            )
            if self._events is not None:
                self._events.write("execution_record", record.request_id, request_id=record.request_id)

    def get(self, request_id: UUID) -> RequestExecutionRecord | None:
        with self._lock:
            row = self._db.connection.execute(
                "SELECT record_json FROM execution_records WHERE request_id = ?",
                (str(request_id),),
            ).fetchone()
            if row is None:
                return None
            if self._events is not None:
                self._events.read("execution_record", request_id, request_id=request_id)
            return execution_record_from_dict(loads(row["record_json"]))

    def list_request_ids(self) -> list[UUID]:
        with self._lock:
            rows = self._db.connection.execute(
                "SELECT request_id FROM execution_records ORDER BY captured_at ASC"
            ).fetchall()
            return [UUID(row["request_id"]) for row in rows]

    def delete(self, request_id: UUID) -> bool:
        with self._lock:
            cursor = self._db.connection.execute(
                "DELETE FROM execution_records WHERE request_id = ?",
                (str(request_id),),
            )
            return cursor.rowcount > 0


class SqliteRequestRepository(_SqliteRepoBase):
    def save_request(self, metadata: RequestMetadata) -> None:
        with self._lock:
            outcome = metadata.terminal_outcome
            self._db.connection.execute(
                """
                INSERT OR REPLACE INTO requests
                (request_id, correlation_id, model, terminal_state, failure_reason, failure_message,
                 batch_id, backend_id, captured_at, payload_json, terminal_outcome_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(metadata.request_id),
                    metadata.correlation_id,
                    metadata.model,
                    metadata.terminal_state,
                    outcome.failure_reason,
                    outcome.failure_message,
                    outcome.batch_id,
                    outcome.backend_id,
                    metadata.captured_at.isoformat(),
                    dumps(payload_snapshot_to_dict(metadata.payload)),
                    dumps(terminal_outcome_to_dict(outcome)),
                ),
            )
            if self._events is not None:
                self._events.write("request", metadata.request_id, request_id=metadata.request_id)

    def get_request(self, request_id: UUID) -> RequestMetadata | None:
        with self._lock:
            row = self._db.connection.execute(
                "SELECT * FROM requests WHERE request_id = ?",
                (str(request_id),),
            ).fetchone()
            if row is None:
                return None
            from gpu_inference_observability.runtime.replay.models import TerminalOutcome

            metadata = RequestMetadata(
                request_id=UUID(row["request_id"]),
                correlation_id=row["correlation_id"],
                model=row["model"],
                terminal_state=row["terminal_state"],
                captured_at=datetime.fromisoformat(row["captured_at"]),
                payload=payload_snapshot_from_dict(loads(row["payload_json"])),
                terminal_outcome=terminal_outcome_from_dict(loads(row["terminal_outcome_json"])),
            )
            if self._events is not None:
                self._events.read("request", request_id, request_id=request_id)
            return metadata

    def list_requests(self) -> list[RequestMetadata]:
        with self._lock:
            rows = self._db.connection.execute(
                "SELECT request_id FROM requests ORDER BY captured_at ASC"
            ).fetchall()
            result: list[RequestMetadata] = []
            for row in rows:
                metadata = self.get_request(UUID(row["request_id"]))
                if metadata is not None:
                    result.append(metadata)
            return result

    def delete_request(self, request_id: UUID) -> bool:
        with self._lock:
            conn = self._db.connection
            conn.execute("DELETE FROM lifecycle_transitions WHERE request_id = ?", (str(request_id),))
            conn.execute("DELETE FROM scheduler_decisions WHERE request_id = ?", (str(request_id),))
            conn.execute("DELETE FROM batch_decisions WHERE request_id = ?", (str(request_id),))
            conn.execute("DELETE FROM failures WHERE request_id = ?", (str(request_id),))
            conn.execute("DELETE FROM trace_summaries WHERE request_id = ?", (str(request_id),))
            conn.execute("DELETE FROM execution_records WHERE request_id = ?", (str(request_id),))
            cursor = conn.execute("DELETE FROM requests WHERE request_id = ?", (str(request_id),))
            return cursor.rowcount > 0


class SqliteLifecycleRepository(_SqliteRepoBase):
    def save_transitions(self, request_id: UUID, transitions: tuple[LifecycleTransition, ...]) -> None:
        with self._lock:
            conn = self._db.connection
            conn.execute("DELETE FROM lifecycle_transitions WHERE request_id = ?", (str(request_id),))
            for transition in transitions:
                conn.execute(
                    """
                    INSERT INTO lifecycle_transitions
                    (request_id, sequence_num, event_type, from_state, to_state, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(transition.request_id),
                        transition.sequence_num,
                        transition.event_type,
                        transition.from_state,
                        transition.to_state,
                        transition.timestamp.isoformat(),
                    ),
                )
            if self._events is not None:
                self._events.write("lifecycle", request_id, request_id=request_id)

    def get_transitions(self, request_id: UUID) -> tuple[LifecycleTransition, ...]:
        with self._lock:
            rows = self._db.connection.execute(
                """
                SELECT request_id, sequence_num, event_type, from_state, to_state, timestamp
                FROM lifecycle_transitions
                WHERE request_id = ?
                ORDER BY sequence_num ASC
                """,
                (str(request_id),),
            ).fetchall()
            return tuple(
                lifecycle_transition_from_dict(
                    {
                        "request_id": row["request_id"],
                        "sequence_num": row["sequence_num"],
                        "event_type": row["event_type"],
                        "from_state": row["from_state"],
                        "to_state": row["to_state"],
                        "timestamp": row["timestamp"],
                    }
                )
                for row in rows
            )


class SqliteSchedulerDecisionRepository(_SqliteRepoBase):
    def save_decisions(self, decisions: tuple[SchedulerDecision, ...]) -> None:
        if not decisions:
            return
        request_id = decisions[0].request_id
        with self._lock:
            conn = self._db.connection
            conn.execute("DELETE FROM scheduler_decisions WHERE request_id = ?", (str(request_id),))
            for decision in decisions:
                conn.execute(
                    """
                    INSERT INTO scheduler_decisions
                    (request_id, sequence_num, event_type, decision_reason, scheduler_cycle_id,
                     batch_id, timestamp, details_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(decision.request_id),
                        decision.sequence_num,
                        decision.event_type,
                        decision.decision_reason,
                        decision.scheduler_cycle_id,
                        decision.batch_id,
                        decision.timestamp.isoformat(),
                        dumps(decision.details),
                    ),
                )
            if self._events is not None:
                self._events.write("scheduler_decision", request_id, request_id=request_id)

    def get_decisions(self, request_id: UUID) -> tuple[SchedulerDecision, ...]:
        with self._lock:
            rows = self._db.connection.execute(
                """
                SELECT request_id, sequence_num, event_type, decision_reason, scheduler_cycle_id,
                       batch_id, timestamp, details_json
                FROM scheduler_decisions
                WHERE request_id = ?
                ORDER BY sequence_num ASC
                """,
                (str(request_id),),
            ).fetchall()
            return tuple(
                scheduler_decision_from_dict(
                    {
                        "request_id": row["request_id"],
                        "sequence_num": row["sequence_num"],
                        "event_type": row["event_type"],
                        "decision_reason": row["decision_reason"],
                        "scheduler_cycle_id": row["scheduler_cycle_id"],
                        "batch_id": row["batch_id"],
                        "timestamp": row["timestamp"],
                        "details": loads(row["details_json"]),
                    }
                )
                for row in rows
            )


class SqliteBatchDecisionRepository(_SqliteRepoBase):
    def save_decisions(self, decisions: tuple[BatchDecision, ...]) -> None:
        if not decisions:
            return
        request_id = decisions[0].request_id
        with self._lock:
            conn = self._db.connection
            conn.execute("DELETE FROM batch_decisions WHERE request_id = ?", (str(request_id),))
            for decision in decisions:
                conn.execute(
                    """
                    INSERT INTO batch_decisions
                    (request_id, sequence_num, event_type, batch_id, decision_reason, timestamp, details_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(decision.request_id),
                        decision.sequence_num,
                        decision.event_type,
                        decision.batch_id,
                        decision.decision_reason,
                        decision.timestamp.isoformat(),
                        dumps(decision.details),
                    ),
                )
            if self._events is not None:
                self._events.write("batch_decision", request_id, request_id=request_id)

    def get_decisions(self, request_id: UUID) -> tuple[BatchDecision, ...]:
        with self._lock:
            rows = self._db.connection.execute(
                """
                SELECT request_id, sequence_num, event_type, batch_id, decision_reason, timestamp, details_json
                FROM batch_decisions
                WHERE request_id = ?
                ORDER BY sequence_num ASC
                """,
                (str(request_id),),
            ).fetchall()
            return tuple(
                batch_decision_from_dict(
                    {
                        "request_id": row["request_id"],
                        "sequence_num": row["sequence_num"],
                        "event_type": row["event_type"],
                        "batch_id": row["batch_id"],
                        "decision_reason": row["decision_reason"],
                        "timestamp": row["timestamp"],
                        "details": loads(row["details_json"]),
                    }
                )
                for row in rows
            )


class SqliteFailureRepository(_SqliteRepoBase):
    def save_failures(self, failures: tuple[PersistedFailureRecord, ...]) -> None:
        with self._lock:
            for failure in failures:
                self._db.connection.execute(
                    """
                    INSERT OR REPLACE INTO failures
                    (failure_id, request_id, failure_type, failure_owner, failure_component,
                     failure_category, failure_reason, failure_state, failure_timestamp,
                     correlation_id, batch_id, backend_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(failure.failure_id),
                        str(failure.request_id),
                        failure.failure_type,
                        failure.failure_owner.value,
                        failure.failure_component,
                        failure.failure_category.value,
                        failure.failure_reason,
                        failure.failure_state,
                        failure.failure_timestamp.isoformat(),
                        failure.correlation_id,
                        failure.batch_id,
                        failure.backend_id,
                    ),
                )
                if self._events is not None:
                    self._events.write("failure", failure.failure_id, request_id=failure.request_id)

    def query_failures(self, *, limit: int = 100) -> list[PersistedFailureRecord]:
        with self._lock:
            rows = self._db.connection.execute(
                """
                SELECT * FROM failures
                ORDER BY failure_timestamp DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [self._row_to_failure(row) for row in rows]

    def query_failures_by_request(self, request_id: UUID) -> list[PersistedFailureRecord]:
        with self._lock:
            rows = self._db.connection.execute(
                "SELECT * FROM failures WHERE request_id = ? ORDER BY failure_timestamp ASC",
                (str(request_id),),
            ).fetchall()
            return [self._row_to_failure(row) for row in rows]

    def query_failures_by_component(self, component: RuntimeComponent) -> list[PersistedFailureRecord]:
        with self._lock:
            rows = self._db.connection.execute(
                "SELECT * FROM failures WHERE failure_owner = ? ORDER BY failure_timestamp DESC",
                (component.value,),
            ).fetchall()
            return [self._row_to_failure(row) for row in rows]

    def _row_to_failure(self, row) -> PersistedFailureRecord:
        return persisted_failure_from_dict(
            {
                "failure_id": row["failure_id"],
                "request_id": row["request_id"],
                "failure_type": row["failure_type"],
                "failure_owner": row["failure_owner"],
                "failure_component": row["failure_component"],
                "failure_category": row["failure_category"],
                "failure_reason": row["failure_reason"],
                "failure_state": row["failure_state"],
                "failure_timestamp": row["failure_timestamp"],
                "correlation_id": row["correlation_id"],
                "batch_id": row["batch_id"],
                "backend_id": row["backend_id"],
            }
        )


class SqliteReplayRepository(_SqliteRepoBase):
    def save_replay(self, replay: ReplayExecution) -> None:
        with self._lock:
            self._db.connection.execute(
                """
                INSERT OR REPLACE INTO replay_executions
                (replay_id, source_request_id, replay_request_id, outcome, terminal_state,
                 failure_reason, failure_message, started_at, completed_at, replay_events_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(replay.replay_id),
                    str(replay.source_request_id) if replay.source_request_id else None,
                    str(replay.replay_request_id),
                    replay.outcome.value,
                    replay.terminal_state,
                    replay.failure_reason,
                    replay.failure_message,
                    replay.started_at.isoformat(),
                    replay.completed_at.isoformat(),
                    dumps(list(replay.replay_events)),
                ),
            )
            if self._events is not None:
                self._events.write("replay", replay.replay_id, request_id=replay.source_request_id)

    def get_replay(self, replay_id: UUID) -> ReplayExecution | None:
        with self._lock:
            row = self._db.connection.execute(
                "SELECT * FROM replay_executions WHERE replay_id = ?",
                (str(replay_id),),
            ).fetchone()
            if row is None:
                return None
            return replay_execution_from_dict(
                {
                    "replay_id": row["replay_id"],
                    "source_request_id": row["source_request_id"],
                    "replay_request_id": row["replay_request_id"],
                    "outcome": row["outcome"],
                    "terminal_state": row["terminal_state"],
                    "failure_reason": row["failure_reason"],
                    "failure_message": row["failure_message"],
                    "started_at": row["started_at"],
                    "completed_at": row["completed_at"],
                    "replay_events": loads(row["replay_events_json"]),
                }
            )

    def list_replays(self, *, source_request_id: UUID | None = None) -> list[ReplayExecution]:
        with self._lock:
            if source_request_id is None:
                rows = self._db.connection.execute(
                    "SELECT replay_id FROM replay_executions ORDER BY completed_at ASC"
                ).fetchall()
            else:
                rows = self._db.connection.execute(
                    "SELECT replay_id FROM replay_executions WHERE source_request_id = ? ORDER BY completed_at ASC",
                    (str(source_request_id),),
                ).fetchall()
            result: list[ReplayExecution] = []
            for row in rows:
                replay = self.get_replay(UUID(row["replay_id"]))
                if replay is not None:
                    result.append(replay)
            return result

    def save_comparison(self, comparison: ReplayComparisonRecord) -> None:
        with self._lock:
            self._db.connection.execute(
                """
                INSERT OR REPLACE INTO replay_comparisons
                (comparison_id, original_request_id, replay_request_id, generated_at,
                 terminal_state_match, matches, differences_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(comparison.comparison_id),
                    str(comparison.original_request_id),
                    str(comparison.replay_request_id),
                    comparison.generated_at.isoformat(),
                    int(comparison.terminal_state_match),
                    int(comparison.matches),
                    dumps(list(comparison.differences)),
                ),
            )
            if self._events is not None:
                self._events.write("replay_comparison", comparison.comparison_id)

    def get_comparison(self, comparison_id: UUID) -> ReplayComparisonRecord | None:
        with self._lock:
            row = self._db.connection.execute(
                "SELECT * FROM replay_comparisons WHERE comparison_id = ?",
                (str(comparison_id),),
            ).fetchone()
            if row is None:
                return None
            return replay_comparison_from_dict(
                {
                    "comparison_id": row["comparison_id"],
                    "original_request_id": row["original_request_id"],
                    "replay_request_id": row["replay_request_id"],
                    "generated_at": row["generated_at"],
                    "terminal_state_match": bool(row["terminal_state_match"]),
                    "matches": bool(row["matches"]),
                    "differences": loads(row["differences_json"]),
                }
            )


class SqliteTraceRepository(_SqliteRepoBase):
    def save_summary(self, summary: TraceSummary) -> None:
        with self._lock:
            self._db.connection.execute(
                """
                INSERT OR REPLACE INTO trace_summaries
                (request_id, correlation_id, event_count, failure_count,
                 stage_durations_json, span_metadata_json, captured_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(summary.request_id),
                    summary.correlation_id,
                    summary.event_count,
                    summary.failure_count,
                    dumps(summary.stage_durations_ms),
                    dumps(trace_summary_to_dict(summary)["span_metadata"]),
                    summary.captured_at.isoformat(),
                ),
            )
            if self._events is not None:
                self._events.write("trace_summary", summary.request_id, request_id=summary.request_id)

    def get_summary(self, request_id: UUID) -> TraceSummary | None:
        with self._lock:
            row = self._db.connection.execute(
                "SELECT * FROM trace_summaries WHERE request_id = ?",
                (str(request_id),),
            ).fetchone()
            if row is None:
                return None
            return trace_summary_from_dict(
                {
                    "request_id": row["request_id"],
                    "correlation_id": row["correlation_id"],
                    "event_count": row["event_count"],
                    "failure_count": row["failure_count"],
                    "stage_durations_ms": loads(row["stage_durations_json"]),
                    "span_metadata": loads(row["span_metadata_json"]),
                    "captured_at": row["captured_at"],
                }
            )
