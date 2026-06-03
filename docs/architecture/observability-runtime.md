# Runtime Observability

**Status:** Implemented (Session 12). Describes in-process tracing only.

**Not implemented:** Prometheus export, Grafana dashboards, OpenTelemetry, HTTP APIs, persistent storage, GPU metrics.

## Problem

After Session 11, a request completes end-to-end but an operator cannot answer:

- What happened?
- Why did it fail?
- How long did each stage take?

Session 12 adds measurement and recording capability. No performance claims are made from these structures.

## Trace Model

### TraceContext

Per-request identifiers propagated across components:

| Field | Set by |
| --- | --- |
| `request_id` | Gateway receive / control plane registration |
| `correlation_id` | `RequestContext.trace_id` from gateway submit |
| `batch_id` | Scheduler batch placement, lifecycle SCHEDULED transition |
| `backend_id` | Adapter dispatch, lifecycle SUBMITTED transition |

Implementation: `packages/observability/src/gpu_inference_observability/runtime/models.py`

`TraceContext` is immutable. `RequestTraceStore` replaces the context object when `batch_id` or `backend_id` arrives on an event.

### RequestTrace

One trace per `request_id`:

- `context`: current `TraceContext`
- `events`: append-only `TraceEvent` list
- `failures`: append-only `FailureRecord` list
- `timestamps`: `LifecycleTimestamps`

### TraceEvent

Every recorded event includes:

- `request_id`
- `correlation_id`
- `timestamp` (UTC)
- `component` (`gateway`, `control_plane`, `scheduler`, `adapter`, `backend`)
- `event_type`

Optional: `batch_id`, `backend_id`, `lifecycle_state`, `decision_reason`, `extra`.

### TraceTimeline

Snapshot built by `TraceInspector.get_request_timeline()`:

- Events sorted by timestamp
- `stage_durations_ms` from `LifecycleTimestamps.durations_ms()`

## Event Model

Central recorder: `RuntimeEventRecorder` writes to `RequestTraceStore`.

| Event record type | Source emitter | Component |
| --- | --- | --- |
| `LifecycleEventRecord` | `LifecycleEventEmitter.emit` | `control_plane` |
| `QueueEventRecord` | `LifecycleEventEmitter.emit_queue` | `control_plane` |
| `SchedulerEventRecord` | `SchedulerEventEmitter.emit` (request-scoped) | `scheduler` |
| `BatchEventRecord` | `BatchEventEmitter.emit` (request-scoped) | `scheduler` |
| `BackendEventRecord` | `BackendEventEmitter.emit` (request-scoped) | `adapter` |
| `FailureEventRecord` | Emitters on failure paths | owning component |

Structured logs continue unchanged. Runtime recording is additive.

## Timing Model

`LifecycleTimestamps` records first-seen UTC time per lifecycle state:

| Field | Lifecycle state |
| --- | --- |
| `request_received_at` | `received` |
| `request_validated_at` | `validated` |
| `request_admitted_at` | `admitted` |
| `request_queued_at` | `queued` |
| `request_scheduled_at` | `scheduled` |
| `request_batched_at` | `batched` |
| `request_submitted_at` | `submitted` |
| `request_completed_at` | `completed` |

Durations (milliseconds):

- `validation_ms`, `admission_ms`, `queue_wait_ms`, `schedule_ms`, `batch_ms`, `submit_ms`, `completion_ms`, `e2e_ms`

Collection point: `TraceInspector.get_request_metrics()` and `get_request_timeline()`.

Units: milliseconds for durations; UTC datetimes for timestamps.

## Metrics Ownership

| Model | Owner | Collection point | Units |
| --- | --- | --- | --- |
| `RequestMetrics` | `TraceInspector` | Derived from trace timestamps and event count | ms, count |
| `QueueMetrics` | `TraceInspector` | Queue events on request trace | count |
| `SchedulerMetrics` | `TraceInspector` | Scheduler events on request trace | count |
| `BatchMetrics` | `TraceInspector` | Batch events + trace context | count |
| `BackendMetrics` | `TraceInspector` | Adapter/backend events + trace context | count |

No external metrics backend. Structures define ownership and units only.

## Failure Ownership

`FailureRecord` fields:

| Field | Meaning |
| --- | --- |
| `failure_type` | Event or category (e.g. `request_failed`, `backend_rejected`, `queue_full`) |
| `failure_owner` | `RuntimeComponent` that recorded the failure |
| `failure_component` | Component string |
| `failure_timestamp` | UTC |
| `failure_reason` | Human-readable reason |
| `failure_state` | Request state at failure (e.g. `failed`, `rejected`, `timed_out`) |

Recorded by:

- Control plane: admission reject, queue full, queue timeout, lifecycle `FAILED`/`REJECTED`
- Adapter: `BATCH_REJECTED` per request in batch

Query: `TraceInspector.get_request_failures(request_id)`.

## Runtime Snapshots

Internal interfaces on `TraceInspector`:

```python
get_request_trace(request_id) -> RequestTrace | None
get_request_timeline(request_id) -> TraceTimeline | None
get_request_metrics(request_id) -> RequestMetrics | None
get_request_failures(request_id) -> list[FailureRecord]
```

Component metrics: `get_queue_metrics`, `get_scheduler_metrics`, `get_batch_metrics`, `get_backend_metrics`.

Wiring: `create_platform_stack()` creates shared `RequestTraceStore`, `RuntimeEventRecorder`, and `TraceInspector`. All embedded services receive the same recorder instance.

## Trace Propagation Path

```
Gateway (record_gateway_receive)
  → Control Plane (lifecycle + queue events)
  → Scheduler (selection events)
  → Batch Engine (batch events)
  → Inference Adapter (backend events)
  → Mock Backend (via adapter result)
```

Validation: `tests/integration/session12_trace_validation.py`

## Limitations

- In-memory only; traces lost on process exit
- Single-process embedded stack; no cross-service RPC propagation
- Scheduler cycle events without `request_id` are logged but not stored on a request trace
- Batch-level backend events without per-request fan-out are not stored (per-request events emitted for submit/accept/reject)
- No sampling, retention policy, or export pipeline

## Related

- Session 3 span context: `gpu_inference_observability.tracing` (separate from runtime `TraceContext`)
- Structured logging: existing service emitters
- Architecture overview: [observability-and-reliability.md](./observability-and-reliability.md)
