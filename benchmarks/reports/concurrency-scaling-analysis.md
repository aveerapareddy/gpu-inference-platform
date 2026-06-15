# Concurrency Scaling Analysis

**Status:** Measured (Session 25)  
**Generated:** 2026-06-15T20:35:32.616643+00:00  

Observed measurements only. No optimization recommendations.

## Methodology

- Workload: `streaming` profile
- Batching: continuous (`max_batch_size=4`, short admission window)
- Concurrency levels tested: 1, 2, 4, 8, 16, 32, 64, 128
- All requests enqueued before scheduling; schedule/complete interleaved
- Telemetry sampled before, during, and after request completion

## Environment

| Field | Value |
|-------|-------|
| OS | Darwin 25.5.0 |
| Python | 3.12.2 |
| GPU source | fallback_unavailable |
| Model | demo |
| Backend | mock |

## Throughput and latency

| Concurrency | requests/s | tokens/s | E2E p50 (ms) | p95 (ms) | p99 (ms) | TTFT p50 (ms) | ITL p50 (ms) | failures |
|-------------|------------|----------|--------------|----------|----------|---------------|--------------|----------|
| 1 | 251.420 | 1005.678 | 0.259 | 0.259 | 0.259 | 0.125 | 0.002 | 0 |
| 2 | 813.573 | 3254.293 | 0.181 | 0.226 | 0.226 | 0.084 | 0.002 | 0 |
| 4 | 1030.198 | 4120.791 | 0.238 | 0.304 | 0.304 | 0.096 | 0.002 | 0 |
| 8 | 1245.265 | 4981.062 | 0.192 | 0.208 | 0.208 | 0.082 | 0.001 | 0 |
| 16 | 821.320 | 3285.280 | 0.195 | 0.225 | 0.228 | 0.085 | 0.001 | 0 |
| 32 | 1075.415 | 4301.659 | 0.183 | 0.197 | 0.213 | 0.082 | 0.001 | 0 |
| 64 | 783.933 | 3135.732 | 0.198 | 0.222 | 0.227 | 0.090 | 0.001 | 0 |
| 128 | 62.193 | 248.774 | 0.203 | 0.248 | 0.270 | 0.092 | 0.001 | 28 |

## Queue and scheduler

| Concurrency | peak queue depth | queue_wait p50 (ms) | scheduling_delay p50 (ms) | scheduler cycles | cycle duration avg (ms) |
|-------------|------------------|---------------------|---------------------------|------------------|-------------------------|
| 1 | 1 | n/a | n/a | 1 | 0.318 |
| 2 | 2 | n/a | n/a | 1 | 0.269 |
| 4 | 4 | n/a | n/a | 1 | 0.373 |
| 8 | 8 | n/a | n/a | 2 | 0.409 |
| 16 | 16 | n/a | n/a | 4 | 1.910 |
| 32 | 32 | n/a | n/a | 8 | 0.722 |
| 64 | 64 | n/a | n/a | 16 | 1.207 |
| 128 | 128 | n/a | n/a | 512 | 0.521 |

## GPU and KV cache

| Concurrency | peak GPU util % | peak GPU mem (bytes) | peak KV occupancy | peak active sequences | KV pressure events |
|-------------|-----------------|----------------------|-------------------|-----------------------|--------------------|
| 1 | 0.000 | 0 | 0.000 | 0 | 0 |
| 2 | 0.000 | 0 | 0.500 | 1 | 0 |
| 4 | 0.000 | 0 | 0.750 | 3 | 0 |
| 8 | 0.000 | 0 | 0.375 | 3 | 0 |
| 16 | 0.000 | 0 | 0.188 | 3 | 0 |
| 32 | 0.000 | 0 | 0.094 | 3 | 0 |
| 64 | 0.000 | 0 | 0.047 | 3 | 0 |
| 128 | 0.000 | 0 | 0.023 | 3 | 0 |

## Bottleneck analysis

| Concurrency | primary bottleneck | evidence |
|-------------|-------------------|----------|
| 1 | `none_observed` | no bottleneck signals above configured thresholds |
| 2 | `none_observed` | no bottleneck signals above configured thresholds |
| 4 | `none_observed` | no bottleneck signals above configured thresholds |
| 8 | `none_observed` | no bottleneck signals above configured thresholds |
| 16 | `scheduler_bound` | scheduler_cycle_duration_ms_p50=1.910 |
| 32 | `none_observed` | no bottleneck signals above configured thresholds |
| 64 | `scheduler_bound` | scheduler_cycle_duration_ms_p50=1.207 |
| 128 | `scheduler_bound` | scheduler_related_failures=28; failed_requests=28 |

## Capacity observations

- Max sustainable concurrency (zero failures): 64

- First concurrency level with failures: 128 (28 failures)

## Run identifiers

- concurrency 1: `c6285943-421d-496a-a417-532277bf74cf`
- concurrency 2: `df509d7f-f0bc-44f8-a637-53c45d11fd99`
- concurrency 4: `dd1ccaf4-157a-45e9-b5a7-88789539f9e0`
- concurrency 8: `0b292c97-1836-4238-826f-c960f1049069`
- concurrency 16: `92987a80-bbd3-42be-98fc-5a2f1b2e97c8`
- concurrency 32: `6dc994d5-565b-4cbc-809d-458e9550d6af`
- concurrency 64: `edd48208-0a51-4662-8a3a-c393cf3f1d41`
- concurrency 128: `4390470e-c185-42ee-9d5c-a93cc0e52c0f`

## Limitations

- Mock backend; not GPU inference capacity
- Bursty admission model
- GPU probe may return fallback zeros
- Bottleneck classification uses configured thresholds on measured signals only
