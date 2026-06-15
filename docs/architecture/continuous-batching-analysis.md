# Continuous Batching Analysis

**Status:** Measured (Session 24)  
**Owner:** benchmarks/runner (batching comparison suite)

This document records observations from measured batching comparison runs. It does not claim universal performance conclusions.

## Measurement scope

- Embedded ValidationStack with mock backend
- Streaming workload profile
- Concurrency levels 2, 4, 8
- Three batching modes: no batching, static batching, continuous batching

Raw tables and run IDs: [continuous-batching-analysis.md](../../benchmarks/reports/continuous-batching-analysis.md)

Charts: `benchmarks/results/batching-comparison/*.svg`

## Observations

Observations below describe measured behavior on the validation host. Values change with hardware, backend, and workload.

### Throughput (requests/s)

At concurrency 8 on the validation host, measured requests/s ordering was:

1. `continuous_batching`
2. `static_batching`
3. `no_batching`

At concurrency 2 and 4, absolute values were close across modes. See report tables for measured numbers.

### TTFT and ITL

Measured from first and subsequent stream chunk arrival times during `stream_inference_request`. Values are wall-clock measurements on the mock streaming path.

### Queue wait and scheduling delay

Queue wait and scheduling delay were derived from lifecycle trace events. With bursty admission (all requests enqueued before scheduling), scheduling delay p50 was near zero for successful requests on the validation host.

Batch member counts at dispatch differed by mode:

- `no_batching`: 1 member per dispatch
- `static_batching`: full batch size at dispatch when concurrency allowed (4 at c4/c8)
- `continuous_batching`: partial or full batches depending on cycle timing

### GPU utilization

GPU probe returned `fallback_unavailable` on the validation host. Reported utilization was 0. KV cache occupancy and active sequence estimates reflected scheduler batch statistics.

## Measured tradeoffs (validation host, mock backend)

| Comparison | Observation |
|------------|-------------|
| Continuous vs no batching | Continuous batching showed higher measured requests/s at concurrency 8 |
| Static vs continuous | Static batching waited for full batches before dispatch; continuous dispatched partial batches earlier |
| No batching | One request per batch; lowest batch utilization at dispatch |

These are observations from one measurement pass. They are not extrapolated to production GPU workloads.

## Limitations

- Mock backend does not execute model inference
- No staggered arrival distribution
- Schedule/complete interleaving required because scheduler allows one active full batch per model
- GPU metrics unavailable without NVML

## Unanswered questions

- Measured impact on real vLLM GPU throughput at identical concurrency
- TTFT/ITL differences under staggered arrivals
- Behavior when concurrency exceeds `max_active_requests`
- Whether observed ordering holds with non-mock backends

## Not implemented

- Scheduler optimization based on these measurements
- Routing changes
- Batching engine redesign
