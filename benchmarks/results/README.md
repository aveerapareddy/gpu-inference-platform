# Benchmark results

**Status:** Implemented (Session 22)  
**Owner:** benchmark runners (embedded, k6, Locust)

Stores persisted `BenchmarkRun` JSON files produced by `benchmarks/runner/store.py`.

Each file includes:

- scenario definition
- hardware and model metadata
- per-request `BenchmarkResult` records
- aggregated `BenchmarkSummary`
- Prometheus metric snapshots (when collected)

Result files are gitignored. They reflect the hardware and configuration at run time. They are not production capacity claims.
