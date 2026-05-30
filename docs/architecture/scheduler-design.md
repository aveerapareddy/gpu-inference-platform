# Scheduler Design

Status: Architecture Phase (Session 1 — design locked)
Implementation: Not Started

This document defines scheduling philosophy, policies, and intended behavior.
It explains why the platform needs a scheduler and what strategy v1 targets.
No algorithms are implemented here.

---

## Why naive serving is insufficient

Naive serving runs one client request per worker invocation: accept connection,
load model context, run full generation, return response, repeat.

Problems at any real load:

- **GPU underutilization**: the GPU sits idle while waiting for I/O and while
  other requests queue at the TCP layer.
- **No backpressure**: excess connections pile up; memory grows with connection
  count; latency becomes unbounded.
- **No fairness**: a few long prompts or greedy clients dominate the worker.
- **No operability**: there is no single place to measure queue depth, reject
  rate, or time-to-first-token under load.

The platform inserts a scheduler so capacity is explicit, overload is visible,
and work is ordered before it touches the GPU.

---

## Why static batching alone is insufficient

Static batching groups N requests and runs them together in one forward pass,
fixed for the duration of the batch.

Limits:

- **Padding waste**: sequences of different lengths pad to the longest in the
  batch; short requests pay for unused compute.
- **Batch rigidity**: a batch cannot shrink until all sequences finish; a single
  long generation blocks the batch slot.
- **Latency coupling**: a new request waits for the current static batch to
  complete or for a new batch window, increasing tail latency.
- **Poor fit for autoregressive decode**: prefill is compute-heavy and parallel;
  decode is memory-bandwidth-heavy and repeated. One static shape does not fit
  both phases well.

Static batching is a reasonable first milestone for request-level grouping, but
it is not the end state for GPU efficiency or tail latency.

---

## Why continuous batching exists

Continuous batching (iteration-level scheduling) treats the running GPU batch as
a set of sequences that can join at prefill and leave at completion. New requests
enter when a slot frees; finished sequences exit without waiting for the whole
batch to end.

**Expected throughput benefits** (qualitative; not benchmark claims):

- Higher GPU duty cycle: fewer idle cycles between batch boundaries.
- Less padding waste on decode steps as sequences complete asynchronously.
- More concurrent sequences within the same memory budget when the backend
  supportsPaged KV and dynamic batching.

**Latency tradeoffs**:

- **TTFT**: a new request may wait for a decode slot in a full batch; admission
  and queue limits bound that wait.
- **ITL**: more sequences in flight can increase memory pressure and slightly
  raise per-step decode time; tuning max batch size is required.
- **Fairness**: without policy, short requests behind long decodes see higher
  ITL; priority classes and queue ordering address this.

Continuous batching is the target execution model behind the adapter interface.
v1 may ship request-level batching first, then enable continuous batching when the
backend exposes slot join/leave. The scheduler philosophy does not change: the
scheduler owns slots and admission; the backend reports capacity.

---

## Scheduling strategy we intend to build

### Layer 1 — Admission and backpressure

Before queueing, every request passes admission:

| Input | Use |
| --- | --- |
| Queue depth per model/priority | Reject when at `max_queue_depth` |
| Free worker slots | Reject when `no_capacity` |
| Global in-flight cap | Protect scheduler and adapter |
| Request limits | Enforce max tokens from control plane |

Outcome: **accept** (enqueue) or **reject** (typed reason + `retry_after_ms`).

Backpressure is explicit rejection, not silent delay beyond configured
`max_queue_wait_ms`. Clients must retry; the system stays predictable.

### Layer 2 — Queue behavior

- Queues are **bounded** per model and priority class.
- Default ordering: **FIFO** within a class.
- **Priority classes**: higher class dequeued first; lower class must not starve
  indefinitely (aging or capped priority depth).
- **Queue wait timeout**: QUEUED -> TIMED_OUT protects against unbounded wait
  when workers are saturated.

### Layer 3 — Batch formation

**Phase A (v1 initial)**: Request-level batching — group compatible requests
(same model, backend constraints) up to `max_batch_size` and dispatch.

**Phase B (v1 target)**: Continuous batching — maintain a running batch per
worker; scheduler assigns sequence slots; adapter maps slots to backend API.

Compatibility rules come from the adapter (e.g., same model, max batch tokens).

### Layer 4 — Dispatch

- Select worker from pool using control-plane routing and observed load.
- Never exceed `max_concurrent_sequences` advertised by the worker.
- Record `worker_id`, `batch_id` on the request for tracing.

### Layer 5 — Cancel and timeout

- Cancel frees slot immediately where backend supports abort.
- Timeouts per state: queue, prefill, decode, e2e (see `runtime-model.md`).

---

## Fairness considerations

| Concern | Approach |
| --- | --- |
| Long prompts blocking decode | Separate prefill queue vs decode slots where backend allows; cap prompt tokens |
| Greedy clients | Per-key rate limit at gateway (planned); global admission cap |
| Priority starvation | Aging in FIFO or round-robin across classes |
| Model isolation | Per-model queues so one model's overload does not fill global queue |

Fairness is observable: per-class queue depth, wait time histograms, and
rejection counters must be sufficient to debug a reported starvation case.

---

## Interaction with backpressure

```
Load increases
  -> queue depth rises
  -> admission rejects at max_queue_depth (REJECTED, queue_full)
  -> clients retry with backoff
  -> queue wait timeouts shed stuck work (TIMED_OUT)
```

The scheduler does not grow unbounded queues to avoid rejecting. That trades
client retry traffic for stable TTFT and ITL on admitted work.

---

## Observability hooks (scheduler-owned)

| Metric | Level |
| --- | --- |
| `scheduler_admission_total` | System |
| `scheduler_queue_depth` | System |
| `scheduler_queue_wait_seconds` | Request |
| `scheduler_batch_size` | Batch |
| `scheduler_dispatch_total` | System |
| Per-request `queue_wait_time`, `scheduling_time` | Request |

Details: `observability-and-reliability.md`.

---

## Scheduler non-responsibilities

- HTTP and SSE to clients
- Model registry writes
- Implementing inference kernels
- Cross-cluster placement
- Autoscaling worker count

---

## Explicit non-goals (scheduler)

- No speculative admission based on predicted load
- No distributed scheduler replicas with shared queue in v1 (single logical scheduler; HA is deployment concern, not multi-region)
- No preemption of in-flight decode except via cancel
- No custom training-data scheduling

---

## Related documents

- States: `runtime-model.md`
- Workflow steps: `../workflows/request-serving-workflow.md`
- Boundaries: `system-overview.md`
