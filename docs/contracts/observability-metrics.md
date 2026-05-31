# Observability Contracts

Status: Architecture Phase (Session 2 — contracts locked)
Implementation: Not Started

Prometheus naming convention: `gpu_inference_<domain>_<name>_<unit>`.
Short names below omit prefix in tables; implementation uses full prefixed names
or documented alias in `packages/observability/contracts/metrics.md`.

Histograms expose `_bucket`, `_sum`, `_count` for percentile queries in PromQL.

## Request metrics

| Name | Type | Unit | Source | Scrape / emit | Purpose |
| --- | --- | --- | --- | --- | --- |
| `request_total` | counter | 1 | gateway, scheduler | on terminal | Count by `status`, `model` |
| `request_ttft_seconds` | histogram | s | gateway | on first SSE byte | TTFT for streaming |
| `request_itl_seconds` | histogram | s | adapter via scheduler | per token | Inter-token latency |
| `request_queue_wait_seconds` | histogram | s | scheduler | on SCHEDULED | Queue wait |
| `request_scheduling_seconds` | histogram | s | scheduler | on prefill start | Schedule to execution |
| `request_completion_seconds` | histogram | s | gateway | on terminal | End-to-end latency |
| `request_tokens_generated_total` | counter | tokens | adapter | on token | Output volume |
| `request_cancelled_total` | counter | 1 | scheduler | on cancel | By `last_state` label |
| `request_failed_total` | counter | 1 | any | on terminal | By `failure_reason` |

Labels (required where applicable): `model`, `backend`, `status`, `failure_reason`,
`priority_class`, `stream`.

Schema record: `request-metrics.json`.

Supports: TTFT, ITL, latency percentiles (from histograms), request failures.

## Batch metrics

| Name | Type | Unit | Source | Scrape / emit | Purpose |
| --- | --- | --- | --- | --- | --- |
| `batch_size` | histogram | sequences | scheduler | on dispatch | Sequences per batch |
| `batch_prefill_seconds` | histogram | s | adapter | on prefill done | Prefill wall time |
| `batch_decode_steps_total` | counter | steps | adapter | per step | Decode iterations |
| `batch_slots_active` | gauge | slots | adapter | 15s | Continuous batch occupancy |
| `batch_dropped_sequences_total` | counter | 1 | adapter | on batch fail | Sequences lost in batch |

Labels: `model`, `worker_id`, `batch_id` (high cardinality: `batch_id` optional
in v1 export to limit cardinality; use sampling policy in implementation).

Supports: batch size distribution, throughput derivation with token counters.

## System metrics

| Name | Type | Unit | Source | Scrape / emit | Purpose |
| --- | --- | --- | --- | --- | --- |
| `scheduler_queue_depth` | gauge | requests | scheduler | 15s | Queue depth |
| `scheduler_admission_total` | counter | 1 | scheduler | on decision | accept/reject by `reason` |
| `scheduler_dispatch_total` | counter | 1 | scheduler | on dispatch | success/fail |
| `gateway_requests_total` | counter | 1 | gateway | on receive | received/validated/rejected |
| `control_plane_lookup_total` | counter | 1 | gateway | on lookup | Registry read outcomes |
| `worker_up` | gauge | 0/1 | control plane | 15s | Worker membership |
| `worker_failures_total` | counter | 1 | scheduler | on worker fail | Crash count |
| `scheduler_state` | gauge | enum | scheduler | 15s | Current SchedulerState encoded as int |
| `throughput_tokens_per_second` | gauge | tokens/s | metrics collector | 15s computed | Derived from token counter rate |

Labels: `model`, `priority`, `worker_id`, `component`.

Supports: queue depth, admission rate, throughput (derived), request failures at
system level.

## GPU metrics

| Name | Type | Unit | Source | Scrape / emit | Purpose |
| --- | --- | --- | --- | --- | --- |
| `gpu_utilization_ratio` | gauge | ratio | node/exporter or backend | 15s | Compute utilization |
| `gpu_memory_used_bytes` | gauge | bytes | node/exporter or backend | 15s | Device memory used |
| `gpu_memory_utilization_ratio` | gauge | ratio | derived or backend | 15s | Used / total memory |
| `inference_prefill_seconds` | histogram | s | adapter | on prefill | Per-model prefill |
| `inference_decode_step_seconds` | histogram | s | adapter | per step | Decode step latency |

Labels: `worker_id`, `model`, `device_id`.

Supports: GPU utilization, GPU memory, prefill/decode timing for capacity planning.

Not a substitute for `request_ttft_seconds` on client-facing SLO analysis.

## Percentile queries (PromQL intent)

| SLO question | Query basis |
| --- | --- |
| TTFT p50/p99 | `histogram_quantile(0.99, request_ttft_seconds_bucket)` |
| ITL p99 | `histogram_quantile(0.99, request_itl_seconds_bucket)` |
| E2E p99 | `histogram_quantile(0.99, request_completion_seconds_bucket)` |
| Queue wait p95 | `histogram_quantile(0.95, request_queue_wait_seconds_bucket)` |

No numeric targets until `benchmarks/results` contains recorded runs.

## Trace attributes (contract)

Each span carries: `request_id`, `model`, `backend`, `worker_id`, `batch_id`
when known. Span names fixed in Session 1 observability doc; unchanged here.

## Log fields (contract)

Required: `timestamp`, `level`, `service`, `request_id`, `message`.
Terminal: `status`, `failure_reason`, `completion_ms`, `ttft_ms`.

## Collection rules

- Counters: monotonic; never decrement.
- Histograms: use native Prometheus buckets; default buckets documented at
  implementation time for sub-second ITL and multi-second TTFT.
- Gauges: point-in-time; `queue_depth` updated on enqueue/dequeue event, not only
  on scrape (exemplar implementation detail; scrape must reflect current value).

## v1 exclusions

- No billing meters
- No per-API-key usage export in metrics (planned gateway counter later)
- No custom trace backend requirement beyond OTLP-compatible export (Future Work)
