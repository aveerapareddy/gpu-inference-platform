# Service Interfaces

Status: Architecture Phase (Session 2 — contracts locked)
Implementation: Not Started

Internal communication uses HTTP/JSON over the service network in v1. Message
bodies reference `packages/common-schemas/schemas/`. No implementation; paths and
behavior only.

Default timeouts apply unless overridden:

| Call type | Timeout | On timeout |
| --- | --- | --- |
| Hot path (submit, stream chunk) | 30s connect; stream unbounded until cancel | Client sees `internal_error` or `timed_out` per policy |
| Control plane read | 2s | Gateway may use cache; reject if stale |
| Control plane write | 5s | Operator retry |
| Dispatch | 10s | Request -> `failed`, worker marked suspect |
| Cancel | 2s | Best-effort; log if adapter does not ack |
| Metrics scrape | 5s | Scrape fails; no impact on serving |

## API Gateway to Control Plane

### GET /internal/v1/models/{model_id}

| | |
| --- | --- |
| **Input** | Path `model_id` |
| **Output** | 200 `ModelRecord` (schema: `model-record.json`) |
| **Behavior** | Return backend binding, limits, pool id |
| **Failure** | 404 `unknown_model`; 503 store unreachable |
| **Timeout** | 2s; gateway cache TTL 30s (configurable) |

### GET /internal/v1/models

List model ids for health checks. Optional in v1.

## API Gateway to Scheduler

### POST /internal/v1/requests

| | |
| --- | --- |
| **Input** | `SubmitRequest`: `inference_request`, `request_context` |
| **Output** | 202 `SubmitResponse`: `request_id`, `state` (`admitted` or `rejected`) |
| **Behavior** | Synchronous admission decision; does not wait for completion |
| **Failure** | 503 scheduler unavailable; 429 `queue_full`; 503 `no_capacity` |
| **Timeout** | 5s |

### POST /internal/v1/requests/{request_id}/cancel

| | |
| --- | --- |
| **Input** | Path `request_id` |
| **Output** | 204 empty |
| **Behavior** | Idempotent cancel |
| **Failure** | 404 unknown id (treat as success for disconnect) |
| **Timeout** | 2s |

### GET /internal/v1/requests/{request_id}/stream (SSE)

| | |
| --- | --- |
| **Input** | Path `request_id` |
| **Output** | SSE stream of `StreamingChunk` |
| **Behavior** | Gateway may open after submit or multiplex on same connection design in implementation |
| **Failure** | Stream ends with error event mapping to `FailureRecord` |
| **Timeout** | Idle stream timeout `e2e_timeout` from config |

Alternative v1 design: submit returns stream handle in body; contract allows
either pattern if schemas are honored.

## Control Plane to Scheduler

Scheduler pulls membership; control plane does not push on hot path in v1.

### GET /internal/v1/workers (scheduler polls)

| | |
| --- | --- |
| **Input** | none |
| **Output** | 200 `WorkerList` |
| **Behavior** | Scheduler refreshes routing table every 5s (configurable) |
| **Failure** | Scheduler uses last snapshot; if none, `unavailable` |
| **Timeout** | 2s |

### POST /internal/v1/workers/register (adapter or worker)

| | |
| --- | --- |
| **Input** | `WorkerRegistration`: `worker_id`, `model_ids`, `capacity` |
| **Output** | 201 |
| **Behavior** | Upsert membership |
| **Failure** | 400 invalid registration |
| **Timeout** | 5s |

## Scheduler to Inference Adapter

### POST /internal/v1/batches

| | |
| --- | --- |
| **Input** | `Batch` schema |
| **Output** | 202 `DispatchAck`: `batch_id`, `state`=`dispatched` |
| **Behavior** | Adapter queues work to backend |
| **Failure** | 503 no backend; 409 capacity race -> scheduler re-queues |
| **Timeout** | 10s |

### POST /internal/v1/batches/{batch_id}/cancel

| | |
| --- | --- |
| **Input** | `batch_id` |
| **Output** | 204 |
| **Behavior** | Cancel all assignments in batch |
| **Failure** | 404 ignored |
| **Timeout** | 2s |

### GET /internal/v1/batches/{batch_id}/stream

| | |
| --- | --- |
| **Output** | SSE `StreamingChunk` multiplexed by `request_id` |
| **Behavior** | Scheduler consumes and routes to gateway |
| **Failure** | `failed` batch state + per-request `FailureRecord` |
| **Timeout** | Per-request decode timeout |

## Inference Adapter to Backend

Backend-specific below the adapter contract. Adapter must implement:

| Operation | Input | Output |
| --- | --- | --- |
| `LoadModel` | model config | ok / error |
| `RunBatch` | backend-native batch handle | stream handle |
| `Stream` | handle | token deltas |
| `Cancel` | handle | ack |
| `Health` | none | ready / not_ready |

Mock backend implements the same interface for development without GPU.

Failure: backend OOM -> `worker_error`; adapter maps to `FailureRecord`.

Timeout: `prefill_timeout`, `decode_timeout` enforced by adapter timer.

## Metrics Collector to Runtime

Pull model (Prometheus). No request-path RPC.

### GET /metrics (each service)

| | |
| --- | --- |
| **Input** | scrape interval 15s default |
| **Output** | Prometheus text per `observability-metrics.md` |
| **Behavior** | Collector or Prometheus scrapes gateway, scheduler, adapter, control plane |
| **Failure** | Missed scrape; gap in charts only |
| **Timeout** | 5s scrape |

### POST /internal/v1/events (optional push path)

| | |
| --- | --- |
| **Input** | `RequestMetrics` or batch of same |
| **Output** | 204 |
| **Behavior** | v1 may use pull-only; push defined for high-cardinality guardrails |
| **Failure** | Drop event; do not block serving |
| **Timeout** | 1s |

## Operator Console (read-only)

Reads scheduler `GET /internal/v1/queue`, control plane models/workers, Prometheus
queries. Not on hot path. Defined in Operations Phase; no new contract beyond
read schemas of `QueueItem` list and `RequestMetrics` summaries.

## Contract versioning

All `/internal/v1/` paths versioned by URL prefix. Breaking schema change increments
v2; v1 supported until migration window documented in release notes.
