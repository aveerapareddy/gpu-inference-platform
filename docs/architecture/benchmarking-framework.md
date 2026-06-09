# Benchmarking Framework

**Status:** Implemented (Session 22)  
**Owner:** benchmarks/ (definitions, runners, persistence)

## Scope

Repeatable benchmark infrastructure for the embedded platform and HTTP load generators. Session 22 implements collection and persistence only. No analysis, tuning, or published performance claims.

## Architecture

```
benchmarks/scenarios/*.json
  ↓
benchmarks/runner/profiles.py (workload profiles)
  ↓
Embedded runner | k6 | Locust
  ↓
Runtime metrics + per-request timings
  ↓
BenchmarkRun JSON → benchmarks/results/
```

Three execution modes:

| Mode | Entry point | Backend |
|------|-------------|---------|
| Embedded | `benchmarks/runner/embedded.py` | In-process ValidationStack per request, mock backend, sequential execution |
| k6 | `benchmarks/load-tests/k6/run.sh` | HTTP against running gateway |
| Locust | `benchmarks/load-tests/locust/run.sh` | HTTP against running gateway |

## Directory layout

| Path | Purpose |
|------|---------|
| `benchmarks/load-tests/` | k6 and Locust harness definitions |
| `benchmarks/scenarios/` | JSON scenario configs |
| `benchmarks/datasets/` | Prompt fixtures |
| `benchmarks/results/` | Persisted run JSON (gitignored) |
| `benchmarks/reports/` | Reserved for future analysis output |
| `benchmarks/runner/` | Python models, runners, store |

## Workload profiles

Defined in `benchmarks/runner/profiles.py`:

| Profile | Input | Output | Stream |
|---------|-------|--------|--------|
| `ShortPromptProfile` | ~10 words | <=32 tokens | no |
| `MediumPromptProfile` | ~80 words | <=128 tokens | no |
| `LongPromptProfile` | ~400 words | <=256 tokens | no |
| `StreamingProfile` | ~10 words | <=64 tokens | yes |
| `MixedProfile` | ~80 words | <=64 tokens | scenario-dependent |

Prompt text loaded from `benchmarks/datasets/prompts.json`.

## Scenarios

| Scenario ID | Concurrency | Requests | Profile |
|-------------|-------------|----------|---------|
| `single_request` | 1 | 1 | short_prompt |
| `low_concurrency` | 2 | 2 | short_prompt |
| `medium_concurrency` | 5 | 5 | medium_prompt |
| `high_concurrency` | 10 | 10 | medium_prompt |
| `streaming_workload` | 2 | 2 | streaming |
| `mixed_workload` | 4 | 4 | mixed |

Configurable via JSON. No tuning parameters in Session 22.

## Result models

Location: `benchmarks/runner/models.py`

| Model | Fields |
|-------|--------|
| `BenchmarkScenario` | scenario_id, concurrency, request_count, workload_profile, stream |
| `BenchmarkResult` | latency_ms, ttft_ms, itl_ms_samples, queue_wait_ms, success, error |
| `BenchmarkSummary` | totals, p50/p99 latency, ttft, throughput_rps, duration |
| `BenchmarkRun` | run_id, scenario, hardware, model, results, summary, metrics_snapshot |
| `HardwareMetadata` | platform, CPU, RAM, GPU model/memory, gpu_source |
| `ModelMetadata` | model_id, backend_id, configuration |

Persistence: `benchmarks/runner/store.py` writes `{run_id}.json`.

## Metrics collection

Embedded runner captures:

- Per-request wall latency (`latency_ms`)
- TTFT and ITL samples on streaming requests (from `StreamSession` timing)
- Queue wait estimate from trace `request_enqueued` / `request_dequeued` events
- Prometheus metric deltas before/after run (`requests_completed_total`, `scheduler_cycles_total`, `request_ttft_seconds`, etc.)

k6 and Locust collect HTTP-level timings only. Platform metrics require separate Prometheus scrape during HTTP runs.

## Hardware metadata

`benchmarks/runner/metadata.py` captures:

- OS platform, Python version, hostname
- CPU model, RAM (via `psutil` when installed)
- GPU device memory via `gpu_inference_observability.gpu.probes` (NVML or fallback)

Metadata is attached to every `BenchmarkRun`. Runs without GPU data still persist with `gpu_source=unavailable`.

## Validation

```bash
python runtime-validation/benchmark_validation.py
```

Validates:

- Profile and scenario definitions
- Embedded single-request and low-concurrency runs
- Streaming workload execution
- Result persistence and metadata capture
- k6/Locust file presence

Uses temporary results directory. Does not publish latency or throughput claims.

## Limitations

- Embedded runner uses mock backend; HTTP runners require manual gateway startup
- Embedded runner creates one ValidationStack per request and executes requests sequentially; `scenario.concurrency` applies only to k6/Locust against a live gateway
- Large-scale k6/Locust runs not executed in CI
- Queue wait and scheduler latency are trace-derived estimates, not span-accurate
- No benchmark comparison or regression detection
- No automatic hardware pinning or environment isolation

## Planned / Not Implemented

- Benchmark analysis and report generation (`benchmarks/reports/`)
- Performance tuning recommendations
- Autoscaling based on benchmark results
- Grafana dashboards for benchmark runs
