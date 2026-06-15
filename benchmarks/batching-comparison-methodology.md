# Batching Comparison Methodology

**Status:** Implemented (Session 24)  
**Owner:** benchmarks/runner/batching_modes.py, batching_comparison.py

## Comparison targets

| Mode | Class | Scheduler configuration |
|------|-------|-------------------------|
| `no_batching` | NoBatchingMode | `max_batch_size=1`, `min_dispatch_members=1` |
| `static_batching` | StaticBatchingMode | `max_batch_size=4`, long admission window, `min_dispatch_members=4` |
| `continuous_batching` | ContinuousBatchingMode | `max_batch_size=4`, short admission window, `min_dispatch_members=1` |

`min_dispatch_members` is implemented on `BatchDispatchService` for benchmark comparisons only. Default is `None` (existing dispatch behavior).

## Workload

| Field | Value |
|-------|-------|
| Profile | `streaming` |
| Scenarios | `batching_comparison_c2`, `batching_comparison_c4`, `batching_comparison_c8` |
| Model | `demo` |
| Backend | mock |

All modes run identical scenario definitions. Request count equals concurrency.

## Runtime configuration

Captured in `BenchmarkRun.batching_config` and `BenchmarkRun.environment`.

| Parameter | Source |
|-----------|--------|
| max_batch_size | mode definition |
| batch_admission_window_ms | mode definition |
| min_dispatch_members | `mode.effective_min_dispatch_members(concurrency)` |
| max_candidate_requests | scenario concurrency |

## Hardware and model configuration

Identical across modes within a validation run. See `BenchmarkEnvironment` on each `BenchmarkRun`.

Set `BENCHMARK_MODEL_SIZE` before running to record model size metadata.

## Execution flow

1. Enqueue all requests for the scenario
2. Repeat until all requests complete:
   - Run one scheduler cycle
   - Record batch member count at first placement
   - Complete placed streaming requests
3. Collect latency, throughput, queue, GPU, and KV cache metrics
4. Persist `BenchmarkRun` JSON
5. Generate report and SVG charts

## Failure behavior

- Request not placed after scheduling rounds: recorded as failed with `request_not_placed_in_batch`
- Static mode at concurrency below `max_batch_size`: `min_dispatch_members` reduced to concurrency
- Runs missing environment metadata are invalid for comparison

## Reproduce

```bash
python runtime-validation/batching_validation.py
```

Outputs:

- `benchmarks/reports/continuous-batching-analysis.md`
- `benchmarks/results/batching-comparison/*.svg`
- Run JSON in temporary directory during validation

## Limitations

- Mock backend; not vLLM GPU inference measurements
- Bursty admission (all requests enqueued before first cycle)
- One active batch per model in scheduler; schedule/complete interleaving required for concurrency > max_batch_size
- GPU metrics depend on host probe availability

## Not implemented

- Staggered arrival load model
- vLLM-backed batching comparison in CI
- Scheduler or routing optimization
