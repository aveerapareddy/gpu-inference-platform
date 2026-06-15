# Concurrency and Capacity Analysis

**Status:** Implemented (Session 25)  
**Owner:** benchmarks/runner (scaling suite, bottleneck framework)

## Scope

Identifies where embedded platform scaling stops and which measured signals correlate with limiting behavior. No runtime optimization.

## Scaling methodology

See [benchmarks/concurrency-scaling-methodology.md](../../benchmarks/concurrency-scaling-methodology.md).

Levels: 1 through 128 by powers of two. Streaming workload. Continuous batching configuration.

## Capacity model

| Signal | Source | Use |
|--------|--------|-----|
| throughput_rps | BenchmarkSummary | requests completed per wall-clock second |
| latency percentiles | BenchmarkSummary | E2E, TTFT, ITL |
| peak_queue_depth | runtime_snapshot | max queue depth during run |
| peak_kv_cache_occupancy_ratio | runtime_snapshot | KV estimate from scheduler sequences |
| peak_gpu_memory_used_bytes | runtime_snapshot | GPU probe sample peak |
| failed_requests | BenchmarkSummary | admission, placement, or execution failures |

Max sustainable concurrency: highest concurrency level with `failed_requests=0` (measured).

## Bottleneck framework

Location: `benchmarks/runner/bottleneck.py`

`BottleneckAnalysis` classifies using measured telemetry only:

| Classification | Trigger (measured) |
|----------------|-------------------|
| `queue_bound` | queue-related failures or queue_wait p50 >= 50% of latency p50 |
| `scheduler_bound` | scheduling_delay p50 >= 1 ms, scheduler failures, or cycle duration avg >= 1 ms |
| `kv_cache_bound` | peak KV occupancy >= 0.85 or kv_cache_pressure_detected events |
| `memory_bound` | peak GPU memory ratio >= 0.90 |
| `gpu_bound` | peak GPU utilization >= 80% |
| `backend_bound` | backend-related failures |
| `none_observed` | no signal above threshold |

Primary bottleneck: first match in priority order (queue, scheduler, KV, memory, GPU, backend).

No speculation beyond configured thresholds applied to observed values.

## Observed behavior (validation host)

Report: [benchmarks/reports/concurrency-scaling-analysis.md](../../benchmarks/reports/concurrency-scaling-analysis.md)

Charts: `benchmarks/results/scaling-analysis/`

On the validation host with mock backend (see generated report for run IDs):

- Max sustainable concurrency with zero failures: 64
- At concurrency 128: 28 failures (`request_not_placed_in_batch`), throughput dropped to ~62 requests/s vs ~784 at concurrency 64
- Primary bottleneck at concurrency 128: `scheduler_bound` (28 scheduler-related failures)
- Primary bottleneck at concurrency 16 and 64: `scheduler_bound` (scheduler cycle duration avg >= 1 ms threshold)
- GPU probe returned fallback zeros; KV occupancy estimates derived from scheduler active sequences
- Throughput peaked around concurrency 8 (~1245 requests/s measured) before plateauing

Re-run validation on target hardware for environment-specific observations.

## Limitations

- Not a production capacity guarantee
- Mock backend does not model GPU saturation
- Bursty admission differs from steady-state production load
- Bottleneck thresholds are configurable constants, not learned models

## Not implemented

- Autoscaling
- Scheduler or routing redesign
- Production max-concurrency SLA
