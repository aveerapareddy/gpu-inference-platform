# Benchmark scenarios

**Status:** Implemented (Session 22)  
**Owner:** benchmarks/scenarios

JSON scenario definitions consumed by `benchmarks/runner/scenarios.py`.

| File | Scenario |
|------|----------|
| `single_request.json` | One synchronous request |
| `low_concurrency.json` | 2 concurrent requests |
| `medium_concurrency.json` | 5 concurrent requests |
| `high_concurrency.json` | 10 concurrent requests |
| `streaming_workload.json` | Streaming requests, concurrency 2 |
| `mixed_workload.json` | Mix of sync and streaming |

Scenarios reference workload profiles in `benchmarks/runner/profiles.py`. No tuning parameters.
