# Request Serving Workflow

Status: Architecture Phase (Session 1 — design locked)
Implementation: Not Started

This document is the authoritative end-to-end description of a single inference
request from client arrival to final token (or terminal failure). Each step
names the owner, data produced, metrics emitted, and possible failures.

For state definitions and transitions, see `docs/architecture/runtime-model.md`.

---

## Workflow (streaming, success path)

```
Client HTTP POST /v1/chat/completions (stream=true)
        |
        v
[1] Gateway: receive and authenticate          state: RECEIVED -> VALIDATED
        |
        v
[2] Gateway: resolve model via control plane     (read registry)
        |
        v
[3] Gateway: submit to scheduler               state: VALIDATED -> ADMITTED
        |
        v
[4] Scheduler: admission control                 ADMITTED -> QUEUED (or SCHEDULED)
        |
        v
[5] Scheduler: queue wait                      state: QUEUED
        |
        v
[6] Scheduler: form batch and dispatch         state: QUEUED -> SCHEDULED
        |
        v
[7] Adapter + worker: prefill                  state: SCHEDULED -> PREFILLING
        |
        v
[8] Adapter + worker: decode                   state: PREFILLING -> DECODING
        |
        v
[9] Gateway: relay SSE tokens                  state: DECODING -> STREAMING
        |
        v
[10] Gateway: send [DONE]                      state: STREAMING -> COMPLETED
```

Non-streaming: steps 1–8 identical; step 9 buffers all tokens; step 10 returns
one JSON body and COMPLETED without client-visible STREAMING.

---

## Step reference

### Step 1 — Gateway receive and validate

| | |
| --- | --- |
| **What happens** | HTTP body parsed; bearer token checked; JSON validated against chat completion schema; `request_id` generated. |
| **Owner** | API gateway |
| **Data produced** | `request_id`, validated internal submit struct, `arrival_time` |
| **Metrics** | `gateway_requests_total{outcome=received}`; validation latency histogram |
| **Failures** | -> REJECTED: invalid JSON, bad key, oversize prompt; -> FAILED: read timeout |

### Step 2 — Model resolution

| | |
| --- | --- |
| **What happens** | Gateway queries control plane for model id: backend binding, max tokens, pool id. |
| **Owner** | API gateway (caller); control plane (authority) |
| **Data produced** | `model`, `backend`, routing hints attached to submit message |
| **Metrics** | `control_plane_lookup_total{result}`; lookup latency |
| **Failures** | -> REJECTED: unknown_model; stale cache beyond policy -> REJECTED or retry once |

### Step 3 — Submit to scheduler

| | |
| --- | --- |
| **What happens** | Gateway sends internal submit RPC with `request_id`, model, messages, stream flag, limits. |
| **Owner** | API gateway |
| **Data produced** | Submit message on wire; gateway holds connection open |
| **Metrics** | `gateway_scheduler_submit_total`; submit latency |
| **Failures** | -> FAILED: scheduler unreachable; -> REJECTED: scheduler immediate deny |

### Step 4 — Admission control

| | |
| --- | --- |
| **What happens** | Scheduler evaluates queue depth, worker capacity, model limits, priority class. Returns accept or reject. |
| **Owner** | Scheduler |
| **Data produced** | Admission decision record; on accept, queue entry |
| **Metrics** | `scheduler_admission_total{decision,reason}`; `scheduler_queue_depth{model,priority}` |
| **Failures** | -> REJECTED: queue_full, no_capacity; accept -> ADMITTED |

### Step 5 — Queue wait

| | |
| --- | --- |
| **What happens** | Request sits in bounded per-model queue until batch slot and worker capacity available. |
| **Owner** | Scheduler |
| **Data produced** | `queue_enter_time`; position metadata for operator console |
| **Metrics** | `scheduler_queue_wait_seconds` histogram; queue depth gauge |
| **Failures** | -> TIMED_OUT: max_queue_wait_ms; -> CANCELLED: client disconnect; -> REJECTED: rare overflow race |

### Step 6 — Schedule and dispatch

| | |
| --- | --- |
| **What happens** | Scheduler selects worker (routing policy + load); forms or joins batch; sends dispatch to adapter. |
| **Owner** | Scheduler |
| **Data produced** | `batch_id`, `worker_id`, `schedule_time`, dispatch command |
| **Metrics** | `scheduler_dispatch_total`; `scheduler_batch_size` histogram; `scheduling_time` recorded on request |
| **Failures** | -> FAILED: dispatch RPC failure; worker gone -> re-queue or FAILED per policy |

### Step 7 — Prefill

| | |
| --- | --- |
| **What happens** | Adapter invokes backend prefill for prompt tokens. GPU memory and compute bound. |
| **Owner** | Inference adapter + worker |
| **Data produced** | KV cache allocated; first-token readiness signal |
| **Metrics** | `inference_prefill_seconds{model,backend}`; GPU utilization (system level) |
| **Failures** | -> FAILED: OOM, backend error; -> TIMED_OUT: prefill_timeout; -> CANCELLED |

### Step 8 — Decode

| | |
| --- | --- |
| **What happens** | Backend generates output tokens stepwise; adapter forwards deltas to scheduler. |
| **Owner** | Inference adapter + worker |
| **Data produced** | Token deltas with sequence index; per-step `ITL` samples |
| **Metrics** | `inference_decode_step_seconds`; `inference_tokens_generated_total`; request `ITL` histogram |
| **Failures** | -> FAILED: worker crash; -> TIMED_OUT: decode_timeout; -> CANCELLED |

### Step 9 — Stream to client

| | |
| --- | --- |
| **What happens** | Scheduler forwards deltas to gateway; gateway emits SSE chunks; first chunk sets TTFT. |
| **Owner** | API gateway (client-facing); scheduler (relay) |
| **Data produced** | SSE events; `first_token_time` |
| **Metrics** | `gateway_stream_tokens_total`; `request_ttft_seconds` (arrival to first SSE) |
| **Failures** | -> CANCELLED: client disconnect; -> FAILED: gateway write error |

### Step 10 — Complete

| | |
| --- | --- |
| **What happens** | Stop condition met; final chunk sent; `[DONE]` for streaming; connection closed cleanly. |
| **Owner** | API gateway |
| **Data produced** | Final `status=completed`, `completion_time`, token count |
| **Metrics** | `request_completed_total{model}`; e2e latency histogram |
| **Failures** | N/A on success path |

---

## Alternate paths

### Rejection (terminal before execution)

```
VALIDATED --[unknown model, validation]--> REJECTED
ADMITTED/QUEUED --[queue_full, no_capacity]--> REJECTED
```

Gateway maps `failure_reason` to HTTP 4xx/429 with stable error body.

### Cancellation

```
Any non-terminal before COMPLETED
        |
        v
Gateway detects disconnect -> cancel RPC -> Scheduler
        |
        +-- QUEUED: drop from queue
        +-- SCHEDULED/PREFILLING/DECODING: adapter cancel -> CANCELLED
```

Metrics: `request_cancelled_total{last_state}`.

### Worker failure mid-flight

```
DECODING --[worker crash]--> FAILED
Scheduler marks worker unhealthy; other requests on worker -> FAILED
```

Metrics: `worker_failures_total`; in-flight `request_failed_total{reason=worker_error}`.

---

## Data flow summary

| Stage | Primary record fields |
| --- | --- |
| After step 1 | `request_id`, `model`, `arrival_time`, `stream` |
| After step 4 | `admission_decision`, `priority_class` |
| After step 5 | `queue_wait_time` |
| After step 6 | `batch_id`, `worker_id`, `backend`, `scheduling_time` |
| After step 9 | `TTFT`, per-token `ITL` |
| After step 10 | `completion_time`, `status`, token_count |

Full field list: `docs/architecture/observability-and-reliability.md`.

---

## Who talks to whom

```
Client <----HTTP----> Gateway
Gateway <----read----> Control Plane
Gateway <----submit/stream----> Scheduler
Scheduler <----dispatch----> Adapter
Adapter <----backend API----> Worker
All ----metrics/traces----> Metrics Collector
Operator Console ----read----> Scheduler, Control Plane, Metrics
```

No other edges on the hot path.

---

## Design locked criteria

This workflow is complete when an engineer can trace any terminal outcome
(REJECTED, FAILED, TIMED_OUT, CANCELLED, COMPLETED) to a specific step and
owner without reading implementation code. Implementation must not add hot-path
edges that bypass these steps.
