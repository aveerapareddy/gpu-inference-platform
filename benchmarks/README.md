# Benchmarks

**Status:** Implemented (Session 22–26)  
**Owner:** benchmarks/ (framework definitions, runners, persisted results)

## Layout

| Directory | Owner | Purpose |
|-----------|-------|---------|
| `load-tests/` | Platform engineers | k6 and Locust load generation definitions |
| `scenarios/` | Platform engineers | Named scenario configs (concurrency, volume, profile) |
| `datasets/` | Platform engineers | Prompt fixtures referenced by profiles |
| `results/` | CI / local runs | Persisted `BenchmarkRun` JSON outputs (gitignored) |
| `reports/` | Future analysis | Human-readable report artifacts (empty until analysis phase) |
| `runner/` | Platform engineers | Python benchmark models, embedded runner, metrics capture |

## Usage

Embedded validation (no HTTP, mock backend):

```bash
python runtime-validation/benchmark_validation.py
python runtime-validation/baseline_validation.py
python runtime-validation/batching_validation.py
python runtime-validation/scaling_validation.py
python runtime-validation/policy_validation.py
```

Baseline report: `benchmarks/reports/baseline-results.md`  
Batching comparison report: `benchmarks/reports/continuous-batching-analysis.md`  
Scaling report: `benchmarks/reports/concurrency-scaling-analysis.md`  
Scheduler policy report: `benchmarks/reports/scheduler-policy-analysis.md`

k6 (requires running gateway):

```bash
./benchmarks/load-tests/k6/run.sh single_request
```

Locust (requires running gateway):

```bash
./benchmarks/load-tests/locust/run.sh --headless -u 2 -r 1 -t 10s
```

Results are written to `benchmarks/results/{run_id}.json`.

## Not implemented

- Benchmark analysis or comparison UI
- Performance tuning or published latency claims
- Large-scale load execution in CI
