# Baseline Performance Results

**Status:** Measured (Session 23)  
**Generated:** 2026-06-09T21:04:48.432787+00:00  
**Runner:** embedded  

This report records collected measurements only. No tuning was applied.

## Methodology

- Embedded ValidationStack with mock backend (`demo` model)
- One stack instance per request; requests within a scenario run sequentially
- Latency measured as wall-clock time per request
- TTFT and ITL measured on streaming requests from `StreamSession` timing
- GPU metrics sampled via `GPUMetricsCollector` after each request
- Input token counts are estimated (`chars/4`); output token counts are measured when backend reports them

## Environment

| Field | Value |
|-------|-------|
| OS | Darwin 25.5.0 |
| Platform | macOS-26.5.1-arm64-arm-64bit |
| Python | 3.12.2 |
| vLLM | not installed |
| CPU | arm |
| RAM | 24.00 GiB |
| GPU | n/a |
| GPU memory | 0 B |
| GPU source | fallback_unavailable |
| Model | demo |
| Model size | n/a |
| Backend | mock |
| Hostname | Akhileshs-Mac-mini.local |

## Reference workloads

| Profile | Est. input tokens | Target output tokens | Stream | Rationale |
|---------|-------------------|----------------------|--------|-----------|
| `short_prompt` | 9 (estimated) | 32 | no | Reference point for low input volume and bounded output |
| `medium_prompt` | 45 (estimated) | 128 | no | Represents typical interactive query length |
| `long_prompt` | 93 (estimated) | 256 | no | Stress input-side token volume without changing backend |
| `streaming` | 9 (estimated) | 64 | yes | Baseline for token delivery latency independent of sync completion path |

## Single-request baseline (concurrency = 1)

| Scenario | Latency (ms) | TTFT (ms) | ITL p50 (ms) | Tokens out | GPU util % | GPU mem used |
|----------|--------------|-----------|--------------|------------|------------|--------------|
| baseline_single_short | 1.313 | n/a | n/a | 0 | 0.000 | 0 B |
| baseline_single_medium | 1.009 | n/a | n/a | 0 | 0.000 | 0 B |
| baseline_single_long | 0.866 | n/a | n/a | 0 | 0.000 | 0 B |
| baseline_single_streaming | 1.221 | 0.920 | 0.028 | 3 | 0.000 | 0 B |

## Low-concurrency measurements

| Scenario | Concurrency | Throughput (rps) | Latency p50 (ms) | p95 (ms) | p99 (ms) | TTFT p50 (ms) | TTFT p95 (ms) | GPU util p50 % |
|----------|-------------|------------------|------------------|----------|----------|---------------|---------------|----------------|
| baseline_concurrency_2 | 2 | 320.954 | 0.838 | 0.903 | 0.903 | n/a | n/a | 0.000 |
| baseline_concurrency_4 | 4 | 315.473 | 0.875 | 0.955 | 0.955 | n/a | n/a | 0.000 |
| baseline_concurrency_8 | 8 | 329.005 | 0.865 | 0.939 | 0.939 | n/a | n/a | 0.000 |

## Run identifiers

- `baseline_single_short`: `7b1213ee-7c08-41e1-b0f1-a34ce43b8456`
- `baseline_single_medium`: `81365c87-6572-4e9d-9974-1f126c8ea43d`
- `baseline_single_long`: `51461e65-8bca-4a7e-bf2a-9f2c1778ef20`
- `baseline_single_streaming`: `28e2950c-b9ad-43db-ac0c-dc1d206491ee`
- `baseline_concurrency_2`: `0f0b5364-58f6-475c-95a9-e101bd39fbfb`
- `baseline_concurrency_4`: `d1a6b60e-fecc-42eb-bb79-664fd244da23`
- `baseline_concurrency_8`: `e06ad6d4-cb45-42da-b3fe-0748bb22079a`

## Limitations

- Measurements use mock backend unless operator configures vLLM backend separately
- Embedded runner does not execute concurrent requests in-process; concurrency scenarios measure sequential request latency aggregates
- GPU metrics reflect host probe state (`nvml`, `fallback_unavailable`, or `simulated`) at sample time
- No comparison or regression analysis in Session 23
