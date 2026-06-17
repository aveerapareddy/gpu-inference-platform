# Scheduler Policy Analysis

**Status:** Measured (Session 26)  
**Generated:** 2026-06-17T03:34:17.690151+00:00  

Observed measurements only. Policy ordering changed; batching and backend held constant.

## Methodology

Fixed runtime configuration across all policies:

| Parameter | Value |
|-----------|-------|
| batching | continuous (`max_batch_size=4`, `admission_window_ms=50`) |
| backend | mock |
| model | demo |
| workload | alternating short (`max_tokens=32`) and long (`max_tokens=256`) |
| priority | cycles DEFAULT / BACKGROUND / ELEVATED per request index |

Policies compared:

| Policy | Selection rule |
|--------|----------------|
| `fifo` | Oldest queued request first; baseline ordering |
| `shortest_job_first` | Smallest estimated_job_tokens first (input estimate + max_tokens) |
| `latency_aware` | Highest queue_wait/age pressure relative to static objectives |
| `fairness` | Deficit fairness across priority_class weights |

Execution flow:

1. Enqueue all requests before scheduling
2. Interleave scheduler cycles and request completion
3. Collect per-request latency, TTFT, ITL, queue wait, scheduling delay

Concurrency levels: 4, 8. Profile id: `mixed_job_sizes`.

## Environment

| Field | Value |
|-------|-------|
| OS | Darwin 25.5.0 |
| Python | 3.12.2 |
| vLLM | not installed |
| GPU source | fallback_unavailable |
| Model | demo |
| Backend | mock |

## Throughput

| Policy | Concurrency | requests/s | tokens/s | failures |
|--------|-------------|------------|----------|----------|
| `fairness` | 4 | 1074.090 | 4296.360 | 0 |
| `fairness` | 8 | 263.283 | 1053.131 | 0 |
| `fifo` | 4 | 734.411 | 2937.644 | 0 |
| `fifo` | 8 | 580.901 | 2323.604 | 0 |
| `latency_aware` | 4 | 1025.214 | 4100.855 | 0 |
| `latency_aware` | 8 | 457.290 | 1829.159 | 0 |
| `shortest_job_first` | 4 | 975.095 | 3900.378 | 0 |
| `shortest_job_first` | 8 | 687.886 | 2751.544 | 0 |

## Latency (ms)

| Policy | Concurrency | E2E p50 | p95 | p99 | TTFT p50 | ITL p50 | queue_wait p50 |
|--------|-------------|---------|-----|-----|----------|---------|----------------|
| `fairness` | 4 | 0.203 | 0.220 | 0.220 | 0.093 | 0.001 | n/a |
| `fairness` | 8 | 0.574 | 0.942 | 0.942 | 0.264 | 0.003 | n/a |
| `fifo` | 4 | 0.258 | 0.271 | 0.271 | 0.106 | 0.002 | n/a |
| `fifo` | 8 | 0.215 | 6.483 | 6.483 | 0.094 | 0.001 | n/a |
| `latency_aware` | 4 | 0.214 | 0.217 | 0.217 | 0.095 | 0.002 | n/a |
| `latency_aware` | 8 | 0.467 | 0.815 | 0.815 | 0.200 | 0.003 | n/a |
| `shortest_job_first` | 4 | 0.243 | 0.271 | 0.271 | 0.101 | 0.002 | n/a |
| `shortest_job_first` | 8 | 0.384 | 0.562 | 0.562 | 0.133 | 0.002 | n/a |

## Scheduling delay and starvation indicators

| Policy | Concurrency | sched_delay p50 | p95 | max | max long-job delay | max queue wait |
|--------|-------------|-----------------|-----|-----|--------------------|----------------|
| `fairness` | 4 | n/a | n/a | n/a | n/a | n/a |
| `fairness` | 8 | n/a | n/a | n/a | n/a | n/a |
| `fifo` | 4 | n/a | n/a | n/a | n/a | n/a |
| `fifo` | 8 | n/a | n/a | n/a | n/a | n/a |
| `latency_aware` | 4 | n/a | n/a | n/a | n/a | n/a |
| `latency_aware` | 8 | n/a | n/a | n/a | n/a | n/a |
| `shortest_job_first` | 4 | n/a | n/a | n/a | n/a | n/a |
| `shortest_job_first` | 8 | n/a | n/a | n/a | n/a | n/a |

## Observed tradeoffs

- Highest throughput observed: `fairness` at concurrency 4 (1074.090 requests/s).
- Lowest E2E p50 latency observed: `fairness` at concurrency 4 (0.203 ms).
- Lowest max long-job scheduling delay observed: `fifo` at concurrency 4 (n/a ms).

## Limitations

- Measurements use mock backend; job-size heuristics do not change mock execution time
- All requests enqueued before scheduling; queue_wait spread is limited
- Fairness policy state resets per benchmark stack instance
- No vLLM or GPU-backed policy runs in this session
- Tradeoff bullets are descriptive comparisons of measured runs, not causal claims
