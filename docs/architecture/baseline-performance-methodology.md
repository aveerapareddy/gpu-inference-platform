# Baseline Performance Methodology

**Status:** Implemented (Session 23)  
**Owner:** benchmarks/runner (baseline suite, report generation)

## Scope

Defines how baseline performance measurements are collected. Session 23 records measurements only. No tuning, optimization, or result interpretation.

## Methodology

### Execution path

1. Load scenario from `benchmarks/scenarios/baseline_*.json`
2. Capture `BenchmarkEnvironment` before requests start
3. For each request: create ValidationStack, startup, execute workload, sample GPU metrics, shutdown
4. Aggregate per-request results into `BenchmarkSummary`
5. Persist `BenchmarkRun` JSON to `benchmarks/results/`
6. Generate `benchmarks/reports/baseline-results.md`

### Runner

Embedded runner (`benchmarks/runner/embedded.py`) with mock backend. HTTP load generators from Session 22 are not used for baseline collection.

### Workload selection

Reference workloads defined in `benchmarks/baseline-workloads.md`:

- Short, medium, long synchronous prompts
- Streaming prompt

Low-concurrency scenarios use short prompt with concurrency 2, 4, and 8. Request count equals concurrency value.

## Measurement definitions

| Metric | Definition | Source |
|--------|------------|--------|
| End-to-end latency | Wall-clock ms from request start to completion | Embedded runner |
| TTFT | Time to first streamed token (ms) | `StreamSession.timing` |
| ITL | Inter-token latency samples (ms) | `StreamSession.timing` |
| Throughput | Successful requests / scenario duration (rps) | `BenchmarkSummary` |
| Latency p50/p95/p99 | Percentiles over successful request latencies | `benchmarks/runner/metrics.py` |
| Tokens generated | Completion or stream token count when reported | Lifecycle entry |
| GPU utilization | Device utilization % at post-request sample | `GPUMetricsCollector` |
| GPU memory used | Device memory used bytes at post-request sample | `GPUMetricsCollector` |
| Input tokens | Estimated via chars/4 | `benchmarks/runner/tokens.py` |

Measured vs estimated:

- Latency, TTFT, ITL, throughput percentiles: **measured**
- Input token counts: **estimated**
- GPU metrics: **measured** when NVML available; **zero/fallback** otherwise

## Environment metadata

Required on every baseline run. See `benchmarks/environment/README.md`.

Runs missing environment metadata must not be used for baseline comparison.

## Reproducibility

To reproduce baseline measurements:

```bash
python runtime-validation/baseline_validation.py
```

This executes all baseline scenarios, persists results to a temporary directory, and writes `benchmarks/reports/baseline-results.md`.

Stored run JSON in `benchmarks/results/` (local, gitignored) includes full raw measurements for comparison.

## Limitations

- Embedded runner executes requests sequentially; concurrency scenarios do not simulate parallel in-process load
- Mock backend does not generate real model tokens on sync path
- GPU metrics depend on host probe availability
- No statistical repeat count; single pass per scenario in validation
- No analysis of why measurements differ across hardware

## Planned / Not Implemented

- Multi-iteration baseline with confidence intervals
- vLLM-backed baseline automation in CI
- Baseline regression detection
- Performance tuning experiments
