# Replay and Debugging

**Status:** Implemented (Session 16). In-memory execution records, replay engine, reconstruction, and comparison.

**Not implemented:** Operator UI, distributed replay, durable persistence, benchmarking, GPU execution changes.

## Purpose

An operator can select a processed request, reconstruct its execution history, replay it on an isolated runtime stack, and compare replay behavior against the original execution.

## Ownership

| Component | Owner module | Responsibility |
| --- | --- | --- |
| `RequestExecutionRecord` | `gpu_inference_observability.runtime.replay.models` | Immutable snapshot of one terminal execution |
| `ExecutionRecordStore` | `gpu_inference_observability.runtime.replay.store` | In-memory record index by `request_id` |
| Capture | `gpu_inference_observability.runtime.replay.capture` | Build record from `TraceInspector` + terminal entry |
| `ReplayEngine` | `gpu_inference_observability.runtime.replay.engine` | Capture, replay via injected execute callback, compare |
| `ReplayDebugService` | `gpu_inference_observability.runtime.replay.debugging` | Internal debugging API (no HTTP) |
| Gateway wiring | `api_gateway.runtime.stack`, `integrated_client` | Store creation; capture after `execute_full_path` |

Replay does not introduce a parallel execution path. Replay invokes the same `execute_full_path` (or lifecycle subset) callback supplied by the caller.

## Execution Record

`RequestExecutionRecord` is captured at terminal state and is the source of truth for replay.

| Field | Source |
| --- | --- |
| `payload` | `SubmitRequest` at capture time (`RequestPayloadSnapshot`) |
| `lifecycle_transitions` | Lifecycle events from trace timeline |
| `queue_events` | Queue event types from timeline |
| `scheduler_events` | Scheduler event types from timeline |
| `batch_events` | Batch event types from timeline |
| `backend_events` | Backend event types from timeline |
| `failures` | `TraceInspector.get_request_failures` |
| `terminal_outcome` | Registry entry state, failure reason, batch/backend IDs |
| `event_timeline` | Full ordered trace events for the request |

Capture entry points:

1. `IntegratedPlatformClient.accept_request` — automatic after successful or failed full-path execution.
2. `ReplayEngine.capture_from_entry(entry)` — manual capture in validation or orchestrator paths that bypass the gateway client.

**Limitation:** Records are in-memory only. Process restart drops all records. No cross-process or cross-node sharing.

## Replay Model

| Type | Role |
| --- | --- |
| `ReplayRequest` | Input: payload snapshot, optional source record, new `replay_id` |
| `ReplayResult` | Outcome, terminal state, new execution record, replay event names |
| `ReplayContext` | Metadata for a replay run (not persisted separately) |
| `ReplayOutcome` | `completed`, `failed`, `rejected`, `timed_out`, `error` |

Replay assigns a new `request_id` and trace context via `clone_payload_for_replay()` to avoid registry collisions with the original request.

Replay modes:

- From execution record: `ReplayEngine.replay_request_from_record(record)`
- From payload snapshot only: `ReplayRequest(payload=..., source_request_id=None)`

Backend behavior is unchanged. Replay uses the mock backend configured on the target stack.

## Replay Engine

`ReplayEngine.replay(replay_request, execute)`:

1. Emit `replay_started`.
2. Build `SubmitRequest` from payload via `submit_from_payload`.
3. Call injected `execute(submit)` — same path as production orchestration.
4. Capture replay execution record.
5. Emit `replay_completed` or `replay_failed`, then `request_replayed` when a source ID exists.

`ReplayEngine.compare(original, replay)` runs `compare_executions` and emits `comparison_generated`.

### Isolated stack requirement

Replay must run on a **fresh runtime stack** with the same backend and failure-injection configuration as the original. Replaying on the same stack leaves queue, batch, and registry state from the original request and produces incorrect scheduler/batch behavior.

Validation pattern:

```text
stack_a: original execution → capture record
stack_b: fresh stack → replay_request(record, execute_full_path)
```

## Request Reconstruction

`reconstruct_request(request_id, execution_store, inspector)` returns `ReconstructedExecution`:

- Original payload
- Lifecycle history
- Scheduler decisions, batch history, backend interactions
- Queue events, failures, terminal outcome

Resolution order:

1. Execution record in `ExecutionRecordStore` if present.
2. Fallback: assemble from `TraceInspector` trace/timeline (no payload if never captured).

Reconstruction is deterministic for a given store and trace snapshot.

## Execution Comparison

`ExecutionComparison` compares original vs replay records.

| Dimension | Comparison |
| --- | --- |
| Terminal | State, failure reason, backend ID |
| Lifecycle | Transition path (`to_state` sequence) |
| Scheduler | Event type sequence |
| Batch | Event type sequence |
| Backend | Event type sequence |
| Execution timeline | `control_plane`, `scheduler`, `adapter`, `backend` events only |

Gateway ingress events and replay metadata events are excluded from timeline comparison. They differ by design between original (gateway path) and replay (direct orchestrator path).

`matches` is true when `differences` is empty. Intentional divergence (e.g. replay with backend rejection injector) produces structured `ExecutionDifference` entries with `kind`, `field`, `original`, `replay`.

## Failure Replay

Replay supports terminal outcomes from:

| Failure class | Validation approach |
| --- | --- |
| Validation rejection | Admission evaluator reject; replay via `process_through_queued` |
| Queue failures | Harness queue corruption/timeout (Session 15 patterns) |
| Scheduler failure | `FailurePoint.SCHEDULER_CRASH` injector |
| Batch failure | Batch engine injection (Session 15) |
| Backend rejection | `FailurePoint.BACKEND_REJECTION` on `InjectableMockBackend` |

Replay remains observable: trace events, structured logs, metrics recorders, and replay-specific events are emitted on the replay stack's trace store.

## Replay Observability

`ReplayEventEmitter` records to structured logs and `RuntimeEventRecorder` when wired.

| Event | When |
| --- | --- |
| `replay_started` | Before execute callback |
| `replay_completed` | Terminal state completed |
| `replay_failed` | Terminal failed/rejected/timed_out or execute exception |
| `request_replayed` | After successful replay when source request ID known |
| `comparison_generated` | After `ReplayEngine.compare` |

Each event includes `request_id`, `replay_id`, and timestamp. Component: `RuntimeComponent.REPLAY`.

## Internal Debugging Interfaces

`ReplayDebugService` (internal only):

| Method | Returns |
| --- | --- |
| `get_execution_record(request_id)` | Stored record or `None` |
| `reconstruct_execution(request_id)` | `ReconstructedExecution` or `None` |
| `replay_request(source, execute)` | `ReplayResult` |
| `compare_execution(original_id, replay_id)` | `ExecutionComparison` (both IDs in same store) |

Cross-stack comparison: pass both `RequestExecutionRecord` instances to `ReplayEngine.compare`.

Wired on `PlatformStack` as `replay_debug` and `replay_engine`. Created in `create_platform_stack()` and `ValidationStack`.

## Validation

Script: `runtime-validation/replay_validation.py`

Scenarios:

1. Successful replay on fresh stack with full comparison match
2. Failed replay (backend rejection) with terminal state match
3. Validation rejection replay
4. Scheduler failure replay
5. Backend rejection replay with trace integrity
6. Execution comparison with intentional divergence

## Limitations

- In-memory storage only; no durability or retention policy.
- No distributed replay across nodes.
- Same-stack replay is unsupported; queue/batch state is not reset.
- Comparison ignores gateway and replay wrapper events; UUIDs and batch IDs will differ across runs.
- No public HTTP API or operator console in Session 16.
- Capture requires terminal entry; in-flight requests have no execution record until completion.
