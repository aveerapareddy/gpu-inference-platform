# Runtime Persistence

**Status:** Implemented (Session 17). SQLite-backed durable storage for execution history, replay, failures, and trace summaries.

**Not implemented:** PostgreSQL, distributed storage, multi-node recovery, backup systems, HA architecture.

## Purpose

Survive process restart while preserving terminal request history, replay records, failure records, and trace summaries. Live queue and scheduling state remain in-memory and are not recovered.

## Architecture

```
Runtime components
        │
        ▼
ReplayEngine / DurableExecutionRecordStore
        │
        ▼
RuntimeRepository (interface)
        │
        ▼
SqliteRuntimeRepository (Session 17 implementation)
        │
        ▼
SQLite file (local, deterministic)
```

The runtime depends on `RuntimeRepository` and repository interfaces. It does not import SQLite directly.

## Ownership

| Component | Module | Responsibility |
| --- | --- | --- |
| `RuntimeRepository` | `persistence.repository` | Facade over all durable stores |
| `ExecutionRecordRepository` | `persistence.repository` | Full `RequestExecutionRecord` blobs |
| `RequestRepository` | `persistence.repository` | Request metadata and terminal outcomes |
| `LifecycleRepository` | `persistence.repository` | Lifecycle transition rows |
| `SchedulerDecisionRepository` | `persistence.repository` | Scheduler decision rows |
| `BatchDecisionRepository` | `persistence.repository` | Batch decision rows |
| `FailureRepository` | `persistence.repository` | Failure records with category |
| `ReplayRepository` | `persistence.repository` | Replay executions and comparisons |
| `TraceRepository` | `persistence.repository` | Trace summaries (not full distributed traces) |
| `SqliteRuntimeRepository` | `persistence.sqlite.runtime_repository` | SQLite implementation |
| `DurableExecutionRecordStore` | `persistence.durable_store` | In-memory cache + durable write-through |
| Wiring | `api_gateway.runtime.stack` | Optional `db_path` on `create_platform_stack()` |

## Persistence Models

| Model | Stored fields |
| --- | --- |
| `RequestMetadata` | `request_id`, payload snapshot, terminal outcome, model, timestamps |
| `LifecycleTransition` | Ordered lifecycle events per request |
| `SchedulerDecision` | Scheduler events with decision reason and cycle ID |
| `BatchDecision` | Batch events with batch ID and decision reason |
| `PersistedFailureRecord` | Failure type, owner, component, category, reason, state, timestamp |
| `TraceSummary` | Event count, failure count, stage durations, span metadata |
| `ReplayExecution` | Replay ID, source ID, outcome, terminal state, timestamps |
| `ReplayComparisonRecord` | Original vs replay comparison snapshot |

Full `RequestExecutionRecord` JSON is stored in `execution_records` for fast reload and replay.

## SQLite Backend

- Module: `gpu_inference_observability.persistence.sqlite`
- Dependency: Python stdlib `sqlite3` only
- Schema version: 1 (`persistence/sqlite/schema.py`)
- Default use: local development and validation via temp file paths

Enable on embedded stack:

```python
stack = create_platform_stack(db_path="/tmp/gpu-inference-runtime.db")
```

On startup with `db_path`:

1. Open or create SQLite database
2. Apply schema migrations
3. `DurableExecutionRecordStore.recover()` loads execution records into memory cache

On shutdown: `runtime_repository.close()` closes the connection.

## Request Persistence

| Method | Behavior |
| --- | --- |
| `requests.save_request(metadata)` | Insert or replace request row |
| `requests.get_request(request_id)` | Load metadata or `None` |
| `requests.list_requests()` | All persisted requests ordered by capture time |
| `requests.delete_request(request_id)` | Delete request and dependent rows |

Triggered automatically when `ReplayEngine` captures a terminal execution record via `persist_execution_record()`.

## Replay Persistence

| Method | Behavior |
| --- | --- |
| `replays.save_replay(replay)` | Persist replay execution outcome |
| `replays.get_replay(replay_id)` | Load replay or `None` |
| `replays.list_replays(source_request_id=...)` | List replays, optionally filtered by source |
| `replays.save_comparison(comparison)` | Persist comparison snapshot |
| `replays.get_comparison(comparison_id)` | Load comparison or `None` |

Replay results are persisted after `ReplayEngine.replay()` completes. Comparisons are persisted after `ReplayEngine.compare()`.

## Failure Persistence

| Method | Behavior |
| --- | --- |
| `failures.save_failures(records)` | Insert or replace failure rows |
| `failures.query_failures(limit=100)` | Recent failures |
| `failures.query_failures_by_request(request_id)` | Failures for one request |
| `failures.query_failures_by_component(component)` | Failures by owning component |

Failure category is derived from `failure_owner` and `failure_type` at persist time (`FailureCategory` enum).

## Trace Persistence

Stores debugging summaries only:

- Event count
- Failure count
- Lifecycle stage durations (`validation_ms`, `queue_wait_ms`, etc.)
- Span metadata derived from trace events (`component:event_type` entries)

Does not store full OpenTelemetry span payloads or cross-process trace propagation state.

## Recovery Model

After restart:

1. New process opens same SQLite file via `db_path`
2. `DurableExecutionRecordStore.recover()` reloads execution records into memory
3. `replay_debug.get_execution_record()` and `reconstruct_execution()` work from recovered records
4. `requests`, `failures`, `traces`, and `replays` tables are readable via `runtime_repository`

Not recovered:

- In-memory request registry
- Queue contents
- Active batches
- Live trace store events from prior process (only persisted summaries and execution records)

Replay after restart requires a fresh runtime stack (Session 16 rule). Payload rehydration coerces JSON-deserialized enums via `normalize_payload_snapshot()`.

## Persistence Observability

`PersistenceEventEmitter` emits:

| Event | When |
| --- | --- |
| `persistence_write` | Entity saved |
| `persistence_read` | Entity loaded |
| `persistence_failure` | Write or read error |
| `persistence_recovery` | Startup recovery from durable store |

Each event includes `entity_type`, `entity_id`, and timestamp. Logged via structured logger; optionally appended to request trace when `request_id` is known.

## Validation

```bash
python runtime-validation/persistence_validation.py
```

Scenarios:

1. Process request, shutdown, restart, reconstruct execution, replay
2. Failed request persistence and failure queries after restart
3. Replay execution persisted and listed after restart
4. Persistence write events recorded on request trace

## Limitations

- SQLite file is single-process. No concurrent multi-node access.
- No PostgreSQL or external database support in Session 17.
- No backup, replication, or retention policy.
- Live scheduling state is lost on restart; only terminal history is durable.
- Trace storage is summary-level, not a distributed trace backend.
- Queue and registry state from control plane remain in-memory.

## Related docs

- Replay: [replay-and-debugging.md](./replay-and-debugging.md)
- Storage design target: [storage-design.md](./storage-design.md)
