# Runtime Model

Status: Architecture Phase (Session 1 — design locked)
Implementation: Not Started

This document defines request lifecycle states, transitions, and runtime roles.
It answers what state a request is in from arrival until completion, failure, or
cancel. Operational behavior only; no implementation code.

## Process roles

| Role | Components | Mutable state |
| --- | --- | --- |
| Edge | API gateway | Per-connection streaming buffer; no queue |
| Coordination | Scheduler | Live queue, batch slots, dispatch map |
| Configuration | Control plane | Registry, routing, membership (durable) |
| Execution | Inference adapter + worker | Backend batch and KV cache |
| Observation | Metrics collector, operator console | None on request path |

## Lifecycle overview

A request moves through platform-owned states until it reaches a terminal state.
Backend execution subdivides into PREFILLING and DECODING while the platform
state may be SCHEDULED or STREAMING.

```
RECEIVED -> VALIDATED -> ADMITTED -> QUEUED -> SCHEDULED
                                              |
                    +-------------------------+
                    v
              PREFILLING -> DECODING -> STREAMING -> COMPLETED

Terminal (from multiple points):
  REJECTED | FAILED | TIMED_OUT | CANCELLED
```

Non-streaming requests skip visible client STREAMING but still pass through
DECODING internally; the gateway buffers until COMPLETED.

## State definitions

### RECEIVED

| Field | Definition |
| --- | --- |
| **Purpose** | Request has entered the gateway process but is not yet validated. |
| **Entry** | TCP/HTTP connection accepted; HTTP handler started. |
| **Exit** | Validation begins, or connection closed before validation. |
| **Transitions** | -> VALIDATED; -> CANCELLED (client disconnect); -> FAILED (protocol error). |
| **Failures** | Malformed HTTP; body read timeout before validation. |

### VALIDATED

| Field | Definition |
| --- | --- |
| **Purpose** | Request passed auth and schema checks; eligible for admission. |
| **Entry** | API key accepted; body matches chat completion schema; model exists in registry (via control plane). |
| **Exit** | Submit sent to scheduler, or rejected before scheduler. |
| **Transitions** | -> ADMITTED (scheduler accepts); -> REJECTED (validation or unknown model); -> CANCELLED. |
| **Failures** | Control plane unreachable and no valid cached model entry; limits exceeded (max tokens, prompt size). |

### ADMITTED

| Field | Definition |
| --- | --- |
| **Purpose** | Scheduler accepted the request; it will enter a queue unless immediately scheduled. |
| **Entry** | Admission control returned accept; `request_id` assigned. |
| **Exit** | Enqueued or immediately scheduled. |
| **Transitions** | -> QUEUED; -> SCHEDULED (zero-queue fast path if capacity available); -> REJECTED (race: queue became full between gateway submit and admit). |
| **Failures** | Scheduler unavailable; internal submit timeout. |

### QUEUED

| Field | Definition |
| --- | --- |
| **Purpose** | Request waits in a bounded queue for capacity and batch slot. |
| **Entry** | Admitted and not yet assigned to a worker batch. |
| **Exit** | Selected for dispatch or removed. |
| **Transitions** | -> SCHEDULED; -> REJECTED (queue wait timeout policy); -> CANCELLED; -> TIMED_OUT. |
| **Failures** | Queue wait exceeds configured `max_queue_wait_ms`; scheduler restart drops queued work (client should retry). |

### SCHEDULED

| Field | Definition |
| --- | --- |
| **Purpose** | Request assigned to a worker batch; dispatch in flight or batch slot reserved. |
| **Entry** | Scheduler placed request in a batch and sent dispatch to adapter. |
| **Exit** | Backend begins prefill, or dispatch fails before execution. |
| **Transitions** | -> PREFILLING; -> FAILED (dispatch error); -> CANCELLED; -> TIMED_OUT. |
| **Failures** | Worker unavailable at dispatch; adapter reject; batch formation timeout. |

### PREFILLING

| Field | Definition |
| --- | --- |
| **Purpose** | Worker processes the prompt (attention over input tokens). Dominated by compute and memory bandwidth on long prompts. |
| **Entry** | Adapter invoked backend prefill for this sequence in the batch. |
| **Exit** | First output token ready or prefill error. |
| **Transitions** | -> DECODING; -> FAILED; -> CANCELLED; -> TIMED_OUT. |
| **Failures** | OOM on worker; backend error; prefill timeout. |

### DECODING

| Field | Definition |
| --- | --- |
| **Purpose** | Worker generates output tokens autoregressively (one or more steps per scheduling iteration). |
| **Entry** | First token produced after prefill. |
| **Exit** | Stop condition met (EOS, max_tokens) or error. |
| **Transitions** | -> STREAMING (first token forwarded to client); -> COMPLETED (non-streaming: all tokens ready); -> FAILED; -> CANCELLED; -> TIMED_OUT. |
| **Failures** | Backend crash mid-decode; decode step timeout; cancel during decode. |

### STREAMING

| Field | Definition |
| --- | --- |
| **Purpose** | Tokens are flowing to the client via gateway SSE. Platform state while at least one token has been sent and completion not yet acknowledged. |
| **Entry** | Gateway sent first SSE chunk to client. |
| **Exit** | Final chunk and `[DONE]` sent, or stream aborted. |
| **Transitions** | -> COMPLETED; -> CANCELLED; -> FAILED (gateway write error). |
| **Failures** | Client disconnect (triggers cancel upstream); gateway cannot write to socket. |

### COMPLETED

| Field | Definition |
| --- | --- |
| **Purpose** | Terminal success. Full response delivered (stream or body). |
| **Entry** | All tokens generated; gateway closed response successfully. |
| **Exit** | None (terminal). |
| **Transitions** | None. |
| **Failures** | N/A. |

### FAILED

| Field | Definition |
| --- | --- |
| **Purpose** | Terminal error after acceptance into the platform path. |
| **Entry** | Unrecoverable error in scheduler, adapter, or worker after ADMITTED. |
| **Exit** | None (terminal). |
| **Transitions** | None. |
| **Failures** | `failure_reason` set (worker_error, adapter_error, internal_error). |

### TIMED_OUT

| Field | Definition |
| --- | --- |
| **Purpose** | Terminal: exceeded a configured deadline (queue wait, prefill, decode, or end-to-end). |
| **Entry** | Timer fired for the active state. |
| **Exit** | None (terminal). |
| **Transitions** | None. |
| **Failures** | `failure_reason` = timeout class (queue_timeout, prefill_timeout, decode_timeout, e2e_timeout). |

### REJECTED

| Field | Definition |
| --- | --- |
| **Purpose** | Terminal: request never entered execution, or was denied at admission. |
| **Entry** | Validation failure, unknown model, queue full, no worker, or admission deny. |
| **Exit** | None (terminal). |
| **Transitions** | None. |
| **Failures** | `failure_reason` = rejection class (validation_error, unknown_model, queue_full, no_capacity). |

### CANCELLED

| Field | Definition |
| --- | --- |
| **Purpose** | Terminal: client or operator cancelled; work stopped and capacity released. |
| **Entry** | Cancel signal from gateway (disconnect or explicit cancel) while non-terminal. |
| **Exit** | None (terminal). |
| **Transitions** | None. |
| **Failures** | N/A (intentional termination). |

## Timing semantics (definitions)

These fields are recorded per request (see `observability-and-reliability.md`):

- **arrival_time**: RECEIVED at gateway.
- **queue_wait_time**: QUEUED entry to SCHEDULED entry.
- **scheduling_time**: SCHEDULED entry to PREFILLING start.
- **TTFT** (time to first token): arrival_time to first token sent in STREAMING (includes queue, schedule, prefill, first decode step).
- **ITL** (inter-token latency): per-token delta during DECODING/STREAMING.
- **completion_time**: COMPLETED timestamp minus arrival_time.

## Streaming and non-streaming

| Mode | Client-visible states | Internal states |
| --- | --- | --- |
| Streaming | STREAMING after first token | Same PREFILLING, DECODING |
| Non-streaming | Stays in gateway buffer until COMPLETED | Same; gateway enters STREAMING only if implementing unified metrics (optional internal STREAMING flag) |

## Cancellation propagation

Cancel can arrive in any non-terminal state. Effect:

| State | Action |
| --- | --- |
| RECEIVED, VALIDATED | Drop; no scheduler submit or best-effort abort submit |
| ADMITTED, QUEUED | Remove from queue; release admission slot |
| SCHEDULED, PREFILLING, DECODING | Signal adapter/worker cancel; free batch slot |
| STREAMING | Stop upstream generation; close SSE |

## Inference backend boundary

The adapter exposes: `submit_batch`, `stream_tokens`, `cancel`. The scheduler
does not know whether the backend uses continuous batching internally; it only
sees capacity slots and token deltas. PREFILLING and DECODING map to backend
phases, not scheduler implementation details.

## Capacity

Workers advertise max concurrent sequences (and optionally max batch tokens).
Scheduler never exceeds advertised capacity. Worker loss: in-flight requests ->
FAILED; worker removed from rotation.

## Related documents

- Boundaries: `system-overview.md`
- Workflow steps: `../workflows/request-serving-workflow.md`
- Scheduling philosophy: `scheduler-design.md`
