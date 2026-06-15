# Concurrency scaling methodology

**Status:** Implemented (Session 25)  
**Owner:** benchmarks/runner/scaling_levels.py, scaling_runner.py

## Test levels

Default ladder: 1, 2, 4, 8, 16, 32, 64, 128.

Adjust `SCALING_LEVELS` or pass `levels=` to the suite runner when hardware or queue limits require a smaller range.

## Workload

| Field | Value |
|-------|-------|
| Profile | `streaming` |
| Model | `demo` |
| Backend | mock (embedded ValidationStack) |
| Batching | continuous (`max_batch_size=4`) |

Request count equals concurrency at each level.

## Runtime configuration

| Parameter | Source |
|-----------|--------|
| max_queue_size | `max(concurrency * 2, 16)` |
| max_candidate_requests | concurrency |
| batch_admission_window_ms | 50 (continuous mode) |
| min_dispatch_members | 1 |

Captured in `BenchmarkRun.environment` and `BenchmarkRun.batching_config`.

## Hardware

Captured in `BenchmarkEnvironment` on every run. Set `BENCHMARK_MODEL_SIZE` to record model size metadata.

## Repeatability

```bash
python runtime-validation/scaling_validation.py
```

Produces:

- `benchmarks/reports/concurrency-scaling-analysis.md`
- `benchmarks/results/scaling-analysis/*.svg`
- Per-level `BenchmarkRun` JSON (temp dir in validation; `benchmarks/results/` locally)

## Failure behavior

- Admission or queue rejections recorded as failed requests
- Unplaced requests after scheduling rounds: `request_not_placed_in_batch`
- Runs missing environment or bottleneck analysis are invalid for capacity comparison

## Limitations

- Mock backend
- Bursty admission (all requests enqueued before first schedule cycle)
- GPU metrics depend on host probe availability

## Not implemented

- Staggered arrival load
- vLLM-backed scaling runs in CI
- Autoscaling
