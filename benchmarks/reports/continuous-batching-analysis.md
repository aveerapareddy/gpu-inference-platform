# Continuous Batching Analysis

**Status:** Measured (Session 24)  
**Generated:** 2026-06-15T01:44:42.808373+00:00  

Observed measurements only. No tuning applied. No causal claims.

## Methodology

Compare three scheduler configurations on identical streaming workloads:

| Mode | max_batch_size | admission_window_ms | min_dispatch_members |
|------|----------------|---------------------|----------------------|
| `no_batching` | 1 | 1 | 1 |
| `static_batching` | 4 | 3600000 | 4 |
| `continuous_batching` | 4 | 50 | 1 |

Execution flow:

1. Enqueue all requests before scheduling
2. Run scheduler cycles until queue empty
3. Complete streaming requests and collect per-request metrics

Concurrency levels: 2, 4, 8. Workload: `streaming` profile.

Estimated input tokens per request: 9 (chars/4 estimate).
Target output tokens: 64.

## Environment

| Field | Value |
|-------|-------|
| OS | Darwin 25.5.0 |
| Python | 3.12.2 |
| vLLM | not installed |
| GPU source | fallback_unavailable |
| Model | demo |
| Backend | mock |

## Throughput measurements

| Mode | Concurrency | requests/s p50 | tokens/s |
|------|-------------|----------------|----------|
| `continuous_batching` | 2 | 793.835 | 3175.339 |
| `continuous_batching` | 4 | 1028.520 | 4114.079 |
| `continuous_batching` | 8 | 1245.427 | 4981.708 |
| `no_batching` | 2 | 527.490 | 2109.960 |
| `no_batching` | 4 | 806.397 | 3225.589 |
| `no_batching` | 8 | 504.325 | 2017.299 |
| `static_batching` | 2 | 923.396 | 3693.586 |
| `static_batching` | 4 | 1140.061 | 4560.246 |
| `static_batching` | 8 | 1297.552 | 5190.206 |

## Latency measurements (ms)

| Mode | Concurrency | E2E p50 | p95 | p99 | TTFT p50 | p95 | p99 | ITL p50 | p95 |
|------|-------------|---------|-----|-----|----------|-----|-----|---------|-----|
| `continuous_batching` | 2 | 0.186 | 0.198 | 0.198 | 0.086 | 0.094 | 0.094 | 0.001 | 0.002 |
| `continuous_batching` | 4 | 0.224 | 0.513 | 0.513 | 0.104 | 0.332 | 0.332 | 0.002 | 0.002 |
| `continuous_batching` | 8 | 0.193 | 0.205 | 0.205 | 0.083 | 0.096 | 0.096 | 0.001 | 0.002 |
| `no_batching` | 2 | 0.221 | 0.265 | 0.265 | 0.092 | 0.117 | 0.117 | 0.002 | 0.002 |
| `no_batching` | 4 | 0.227 | 0.238 | 0.238 | 0.095 | 0.099 | 0.099 | 0.001 | 0.002 |
| `no_batching` | 8 | 0.208 | 0.232 | 0.232 | 0.089 | 0.097 | 0.097 | 0.001 | 0.002 |
| `static_batching` | 2 | 0.178 | 0.203 | 0.203 | 0.084 | 0.101 | 0.101 | 0.001 | 0.002 |
| `static_batching` | 4 | 0.223 | 0.236 | 0.236 | 0.097 | 0.112 | 0.112 | 0.001 | 0.002 |
| `static_batching` | 8 | 0.180 | 0.218 | 0.218 | 0.082 | 0.094 | 0.094 | 0.001 | 0.002 |

## Queue impact

| Mode | Concurrency | queue_wait p50 (ms) | scheduling_delay p50 (ms) | request_age p50 (ms) | queue_depth at schedule |
|------|-------------|---------------------|---------------------------|----------------------|-------------------------|
| `continuous_batching` | 2 | n/a | n/a | 1.346 | 2 |
| `continuous_batching` | 4 | n/a | n/a | 1.912 | 4 |
| `continuous_batching` | 8 | n/a | n/a | 3.861 | 8 |
| `no_batching` | 2 | n/a | n/a | 2.099 | 2 |
| `no_batching` | 4 | n/a | n/a | 2.800 | 4 |
| `no_batching` | 8 | n/a | n/a | 5.134 | 8 |
| `static_batching` | 2 | n/a | n/a | 1.134 | 2 |
| `static_batching` | 4 | n/a | n/a | 1.909 | 4 |
| `static_batching` | 8 | n/a | n/a | 3.771 | 8 |

## GPU utilization comparison

| Mode | Concurrency | GPU util p50 % | GPU mem p50 (bytes) | KV occupancy p50 | active sequences p50 |
|------|-------------|----------------|---------------------|------------------|----------------------|
| `continuous_batching` | 2 | 0.000 | 0 | 0.000 | 0 |
| `continuous_batching` | 4 | 0.000 | 0 | 0.500 | 2 |
| `continuous_batching` | 8 | 0.000 | 0 | 0.250 | 2 |
| `no_batching` | 2 | 0.000 | 0 | 0.000 | 0 |
| `no_batching` | 4 | 0.000 | 0 | 0.000 | 0 |
| `no_batching` | 8 | 0.000 | 0 | 0.000 | 0 |
| `static_batching` | 2 | 0.000 | 0 | 0.000 | 0 |
| `static_batching` | 4 | 0.000 | 0 | 0.500 | 2 |
| `static_batching` | 8 | 0.000 | 0 | 0.250 | 2 |

## Batch dispatch observations

| Mode | Concurrency | batch members at dispatch (per request) |
|------|-------------|----------------------------------------|
| `continuous_batching` | 2 | 2, 2 |
| `continuous_batching` | 4 | 4, 4, 4, 4 |
| `continuous_batching` | 8 | 4, 4, 4, 4, 4, 4, 4, 4 |
| `no_batching` | 2 | 1, 1 |
| `no_batching` | 4 | 1, 1, 1, 1 |
| `no_batching` | 8 | 1, 1, 1, 1, 1, 1, 1, 1 |
| `static_batching` | 2 | 2, 2 |
| `static_batching` | 4 | 4, 4, 4, 4 |
| `static_batching` | 8 | 4, 4, 4, 4, 4, 4, 4, 4 |

## Run identifiers

- `no_batching` / `batching_comparison_c2`: `197400db-95c1-4430-8287-fb9a7ffe2ed3`
- `static_batching` / `batching_comparison_c2`: `e459f6f5-f81a-4b1c-a1c8-303a204a342f`
- `continuous_batching` / `batching_comparison_c2`: `574876fd-a114-47c0-91e6-40b0df8138f6`
- `no_batching` / `batching_comparison_c4`: `836cf458-922e-4bd3-9ce5-1f714a02b65f`
- `static_batching` / `batching_comparison_c4`: `bb824c4f-788d-481b-b8b6-4828fb462db0`
- `continuous_batching` / `batching_comparison_c4`: `ca972289-b1cb-4d94-bf1d-1a90b9f847c7`
- `no_batching` / `batching_comparison_c8`: `c9ebc776-1cdc-4c5f-a4a5-a856f5792550`
- `static_batching` / `batching_comparison_c8`: `9ca32626-6726-4a2d-9fd8-42ef1eb58cde`
- `continuous_batching` / `batching_comparison_c8`: `d040a4aa-ad20-4ca2-ae70-10df9bb2ef25`

## Limitations

- Mock backend; measurements reflect scheduler and platform path behavior
- All requests enqueued before first scheduling cycle; not a staggered arrival model
- Static mode requires min_dispatch_members instrumentation on BatchDispatchService
- GPU metrics depend on host probe availability
- No universal throughput or latency conclusions drawn in this report
