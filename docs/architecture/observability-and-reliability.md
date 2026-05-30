# Observability and Reliability

Status: Architecture Phase (Session 1 — design locked)
Implementation: Not Started

This document defines the observability model: per-request records, metric
levels, and reliability expectations. No metric values are claimed as measured.

---

## Per-request record

Every request that reaches RECEIVED should produce a record (log + trace +
metrics labels) with these fields when applicable:

| Field | When set | Definition |
| --- | --- | --- |
| `request_id` | Step 1 (gateway) | Unique id for entire path; propagated in all spans and logs |
| `model` | Step 2 | Resolved model id from control plane |
| `backend` | Step 2 or 6 | Inference backend binding (e.g., vllm, mock) |
| `arrival_time` | Step 1 | Timestamp at RECEIVED |
| `queue_wait_time` | Step 5 exit | SCHEDULED time minus QUEUED entry time |
| `scheduling_time` | Step 6 | PREFILLING start minus SCHEDULED entry |
| `TTFT` | Step 9 | First token to client minus `arrival_time` |
| `ITL` | Step 8–9 | Per-token latency samples during decode/stream |
| `completion_time` | Terminal | Terminal timestamp minus `arrival_time` |
| `status` | Terminal | completed, failed, timed_out, rejected, cancelled |
| `failure_reason` | Terminal if not completed | Stable enum (see below) |
| `worker_id` | Step 6 | Assigned worker |
| `batch_id` | Step 6 | Batch identifier |
| `stream` | Step 1 | Client requested streaming or not |
| `priority_class` | Step 4 | Admission class |
| `token_count` | COMPLETED | Output tokens generated |

### failure_reason (stable enum)

| Value | Typical terminal state |
| --- | --- |
| `validation_error` | REJECTED |
| `unknown_model` | REJECTED |
| `queue_full` | REJECTED |
| `no_capacity` | REJECTED |
| `queue_timeout` | TIMED_OUT |
| `prefill_timeout` | TIMED_OUT |
| `decode_timeout` | TIMED_OUT |
| `e2e_timeout` | TIMED_OUT |
| `worker_error` | FAILED |
| `adapter_error` | FAILED |
| `internal_error` | FAILED |
| `client_cancel` | CANCELLED |

---

## Metric levels

### Request level

Attached to `request_id`; used for SLO debugging and operator console rows.

| Metric / field | Type | Notes |
| --- | --- | --- |
| `request_total{status,model}` | Counter | Terminal outcomes |
| `request_ttft_seconds` | Histogram | arrival -> first client token |
| `request_itl_seconds` | Histogram | per-token during decode |
| `request_queue_wait_seconds` | Histogram | QUEUED duration |
| `request_scheduling_seconds` | Histogram | SCHEDULED -> prefill start |
| `request_completion_seconds` | Histogram | e2e latency |
| `request_tokens_generated` | Counter | output tokens |
| `request_cancelled_total{last_state}` | Counter | cancel by last platform state |

### Batch level

Attached to `batch_id` and `worker_id`; scheduler and adapter emit.

| Metric | Type | Notes |
| --- | --- | --- |
| `batch_size` | Histogram | sequences per dispatch |
| `batch_prefill_seconds` | Histogram | batch prefill wall time |
| `batch_decode_steps_total` | Counter | decode iterations |
| `batch_slots_active` | Gauge | continuous batching: used slots |
| `batch_dropped_sequences_total` | Counter | failures inside batch |

### System level

Aggregated across the platform; no `request_id` required.

| Metric | Type | Notes |
| --- | --- | --- |
| `scheduler_queue_depth{model,priority}` | Gauge | current queue |
| `scheduler_admission_total{decision,reason}` | Counter | accept/reject |
| `scheduler_dispatch_total{result}` | Counter | dispatch outcomes |
| `gateway_requests_total{outcome}` | Counter | received/validated/rejected |
| `worker_up{worker_id}` | Gauge | membership health |
| `worker_failures_total` | Counter | worker crashes |
| `control_plane_lookup_total{result}` | Counter | registry reads |

### GPU level

From backend or node exporter where available; labeled by `worker_id`, `model`.

| Metric | Type | Notes |
| --- | --- | --- |
| `gpu_utilization_ratio` | Gauge | compute utilization |
| `gpu_memory_used_bytes` | Gauge | device memory |
| `gpu_memory_utilization_ratio` | Gauge | fraction of device memory |
| `inference_prefill_seconds` | Histogram | backend-reported prefill |
| `inference_decode_step_seconds` | Histogram | per decode step |

GPU metrics inform capacity planning; they do not replace request-level TTFT/ITL
for client-facing latency analysis.

---

## Traces

One trace per `request_id`. Minimum spans:

| Span | Owner |
| --- | --- |
| `gateway.receive` | API gateway |
| `gateway.validate` | API gateway |
| `control_plane.resolve_model` | Control plane |
| `scheduler.admit` | Scheduler |
| `scheduler.queue_wait` | Scheduler |
| `scheduler.dispatch` | Scheduler |
| `adapter.prefill` | Inference adapter |
| `adapter.decode` | Inference adapter |
| `gateway.stream` | API gateway |

Span attributes carry `model`, `backend`, `worker_id`, `batch_id`, `failure_reason`.

---

## Logs

Structured JSON; every line includes `request_id`, `service`, `level`, `message`.
Terminal log includes `status`, `failure_reason`, `completion_time`, `TTFT`.

---

## Reliability expectations

| Behavior | Mechanism |
| --- | --- |
| Bounded latency under overload | Admission reject + queue timeout |
| Typed failures | `failure_reason` on all non-success terminals |
| Worker isolation | FAILED for in-flight on dead worker; stop dispatch |
| Degradation | Shed load via REJECTED; protect admitted TTFT/ITL |
| Observability gap != outage | Metrics collector down does not block serving |

Health: each service exposes `/health` (alive) and `/ready` where applicable.
Scheduler ready requires at least one healthy worker for the requested model.

---

## Operator console (read model)

Displays recent requests with: `request_id`, `model`, `status`, `queue_wait_time`,
`TTFT`, `completion_time`, `failure_reason`, `worker_id`. Live queue depth and
worker_up from system metrics.

---

## v1 observability non-goals

- No billing or usage metering product
- No long-term trace retention beyond demo defaults
- No alerting SaaS; example Prometheus rules only
- No log warehouse integration
- No SLO dashboard with committed numeric targets until benchmarks exist

---

## Related documents

- Workflow steps and per-step metrics: `../workflows/request-serving-workflow.md`
- Lifecycle states: `runtime-model.md`
- Scheduler metrics: `scheduler-design.md`
