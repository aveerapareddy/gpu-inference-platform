# System Overview

Status: Architecture Phase (Session 1 — design locked)
Implementation: Not Started

This document defines the platform structure, component boundaries, and v1
non-goals. It is the authoritative boundary reference before implementation.
Nothing here describes running software.

## Purpose

Provide predictable LLM serving on GPU hardware. Clients send OpenAI-compatible
requests; the platform validates, admits, queues, schedules, and runs them on
inference workers, returning streamed or complete responses. The end-to-end
answer to "what happens from arrival to the final token" is in
`docs/workflows/request-serving-workflow.md` and `docs/architecture/runtime-model.md`.

## Request path (summary)

```
Client
  -> API Gateway (validate, authenticate, stream relay)
  -> Control Plane (model and pool resolution, read-only at request time)
  -> Scheduler (admit, queue, schedule, dispatch)
  -> Inference Adapter -> Worker (prefill, decode, token stream)
  -> Scheduler -> API Gateway -> Client
```

The metrics collector observes every stage. The operator console reads state; it
does not participate in the request path.

## System boundaries

### API Gateway

| | |
| --- | --- |
| **Responsibilities** | Terminate client HTTP; authenticate API keys; validate request bodies against shared schemas; resolve model availability via control plane; submit work to the scheduler; hold the client connection; relay token stream (SSE) or collect stream for non-streaming; detect client disconnect and propagate cancel; map internal errors to OpenAI-compatible HTTP responses. |
| **Inputs** | Client HTTP requests (`POST /v1/chat/completions`); control-plane model registry responses; scheduler submit/response streams; cancel signals from closed connections. |
| **Outputs** | Validated internal submit messages to the scheduler; HTTP responses (stream or body) to the client; per-request spans and metrics; cancel signals to the scheduler. |
| **Non-responsibilities** | Admission decisions; queueing; batching; worker selection; inference execution; persistence of request payloads; billing or user accounts. |
| **Failure boundary** | Gateway failure affects only connections on that instance. In-flight work continues in the scheduler and workers. The gateway does not retry scheduler or worker calls on behalf of the client without an explicit policy. Validation and auth failures never reach the scheduler. |

### Control Plane

| | |
| --- | --- |
| **Responsibilities** | Own model registry (id, backend binding, limits); routing policy (which pool serves which model); worker pool membership and health registration; runtime configuration (queue limits, priority classes, admission thresholds). Serve read APIs used at request time and write APIs used by operators. |
| **Inputs** | Operator configuration changes; worker registration and heartbeat events; scheduler membership queries. |
| **Outputs** | Model metadata and routing decisions to gateway and scheduler; membership snapshots to scheduler; configuration version for cache invalidation. |
| **Non-responsibilities** | Per-request admission; queue state; dispatch; token streaming; metrics aggregation. |
| **Failure boundary** | Control plane outage blocks new model resolution and membership updates. The scheduler may serve from a cached snapshot with documented staleness limits. In-flight requests are not aborted solely because the control plane is unreachable. |

### Scheduler

| | |
| --- | --- |
| **Responsibilities** | Admission control (accept, queue, reject); bounded queueing per model and priority class; batch formation and continuous-batch slot management; dispatch to workers within advertised capacity; propagate cancel to adapter/worker; record per-request scheduling metadata; emit scheduling metrics. Sole authority for assigning work to a worker. |
| **Inputs** | Submit messages from gateway; cancel messages from gateway; worker capacity and load from adapter/control plane; routing and limits from control plane. |
| **Outputs** | Admission responses (accept/reject with reason); dispatch commands to inference adapter; internal request state transitions; scheduling and queue metrics; trace spans for admit, queue, schedule, dispatch. |
| **Non-responsibilities** | HTTP client handling; schema validation of raw client JSON; model registry writes; inference kernel execution; long-term storage of requests. |
| **Failure boundary** | Scheduler failure stops new dispatch and may fail in-flight assignments after timeout. Queued state in memory is lost on restart (accepted tradeoff). No component bypasses the scheduler to reach a worker. |

### Inference Adapter

| | |
| --- | --- |
| **Responsibilities** | Translate scheduler dispatch commands into backend-specific calls; normalize token streams and completion signals; report worker capacity and health; implement cancel on the backend; surface backend failure reasons in a stable internal vocabulary. |
| **Inputs** | Dispatch commands from scheduler; cancel commands from scheduler; backend registration from workers. |
| **Outputs** | Token deltas and completion events to scheduler; worker capacity advertisements; backend-labeled metrics (prefill latency, decode step time where available). |
| **Non-responsibilities** | Admission or queue ordering; client HTTP; model registry; cross-worker routing policy. |
| **Failure boundary** | Adapter failure on a path fails requests assigned to that adapter instance; scheduler marks affected worker unhealthy and stops dispatch. Adapter does not buffer unbounded work independent of scheduler limits. |

### Metrics Collector

| | |
| --- | --- |
| **Responsibilities** | Receive metrics and traces from all services; aggregate and expose for Prometheus; optional trace backend export. Enforce consistent label conventions from `packages/observability`. |
| **Inputs** | Push or scrape from gateway, scheduler, adapter, control plane. |
| **Outputs** | Prometheus-compatible metrics; trace store export; no feedback into the request path. |
| **Non-responsibilities** | Request routing; scheduling; alerting product UI; log storage (logs remain at origin services). |
| **Failure boundary** | Metrics collector outage does not block serving. Observability gaps are operational risk, not request-path failure. |

### Operator Console

| | |
| --- | --- |
| **Responsibilities** | Read-only view of queue depth, worker status, recent requests (id, model, status, timing summary), and admission rejection rates. Support debugging workflows in `docs/runbooks/local-runbook.md`. |
| **Inputs** | Read APIs from scheduler, control plane, metrics collector (or direct Prometheus queries). |
| **Outputs** | UI or API for operators; no writes to runtime request state. |
| **Non-responsibilities** | Configuration changes (those go through control plane APIs); dispatch; cancel; client-facing API. |
| **Failure boundary** | Console outage has no effect on serving. |

## Shared packages

- `packages/common-schemas`: cross-service contracts (client request, internal submit, admission response, token delta, error types, observability field names).
- `packages/observability`: shared instrumentation so all services emit the same labels and trace structure.

## Communication rules

- Services talk over network APIs using `common-schemas` types only.
- Gateway never calls workers or adapter directly.
- Scheduler is the only dispatcher to the adapter.
- Control plane is read on the hot path; writes are operator-driven, not per-token.

## v1 non-goals

The following are out of scope for the first complete version. They are not
deferred bugs; they are intentional exclusions.

| Area | v1 will not |
| --- | --- |
| Model | Train, fine-tune, or ship weights |
| Inference engine | Implement custom CUDA kernels or a transformer from scratch |
| Scale | Distributed scheduling across clusters; multi-region deployment |
| Product | Billing, accounts, authentication platform, RAG, agent framework |
| Operations | Autoscaling controller; predictive admission |
| Safety | Content moderation or output safety classification |
| Data | Conversation history store; analytics warehouse |

Scope discipline is required so the serving path (admit, queue, schedule, stream)
reaches completion on one cluster before scope expands.

## Related documents

- Request states: `runtime-model.md`
- Step-by-step path: `../workflows/request-serving-workflow.md`
- Scheduling strategy: `scheduler-design.md`
- Per-request observability: `observability-and-reliability.md`
- Tradeoffs: `tradeoffs.md`
