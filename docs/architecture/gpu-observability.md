# GPU Observability

**Status:** Implemented (Session 21)  
**Owner:** gpu_inference_observability.gpu (collection, models, events); api-gateway (runtime context wiring)

## Scope

This document describes GPU telemetry, KV cache estimates, memory accounting, and capacity visibility for the embedded platform stack. It does not cover autoscaling, scheduling changes, benchmarking, or operator UI.

## Architecture

```
PlatformRuntimeContext (active requests, sequences, batches)
  ↓
GPUMetricsCollector
  ├── GPUProbe (NVML | fallback | simulated)
  ├── KV cache estimator
  ├── Memory accounting
  ├── Capacity model
  ├── CapacityEventEmitter
  └── RuntimeMetricsRecorder → Prometheus
```

Collection runs on `PlatformStack.startup()` and can be invoked on demand. Metrics export through existing `GET /metrics`.

## GPU Metrics Collector

Location: `packages/observability/src/gpu_inference_observability/gpu/collector.py`

**Probes** (`gpu/probes.py`):

| Probe | When used |
|-------|-----------|
| `NVMLGPUProbe` | `pynvml` available and NVML init succeeds |
| `FallbackGPUProbe` | No GPU or NVML failure; returns zeros, `source=fallback_unavailable` |
| `SimulatedGPUProbe` | Validation only |

Collected per device:

- `utilization_percent`
- `memory_used_bytes`
- `memory_free_bytes`
- `memory_total_bytes`

Optional dependency: `pip install gpu-inference-observability[gpu]` (`nvidia-ml-py`).

## KV Cache Model

Location: `packages/observability/src/gpu_inference_observability/gpu/kv_cache.py`

**Assumption:** The platform does not read vLLM internal KV block counters in Session 21. Estimates use active sequence count from scheduler batch statistics.

**Formula:**

```
estimated_kv_bytes = active_sequences * bytes_per_sequence
cache_occupancy_ratio = active_sequences / max_concurrent_sequences
cache_entries = active_sequences (1:1 mapping assumed)
```

Default `bytes_per_sequence = 65536` (64 KiB). Documented as a platform constant, not a measured per-model value.

**Tracked fields (`KVCacheMetrics`):**

- `cache_entries`
- `active_sequences`
- `cache_occupancy_ratio`
- `estimated_kv_bytes`
- `estimation_method`
- `bytes_per_sequence`

No accuracy claims are made for estimated KV bytes.

## Memory Accounting

Location: `packages/observability/src/gpu_inference_observability/gpu/memory.py`

**Breakdown fields (`MemoryBreakdown`):**

| Field | Source |
|-------|--------|
| `model_weights_bytes` | Default 4 GiB constant (configurable input) |
| `kv_cache_bytes` | From KV cache estimator |
| `runtime_overhead_bytes` | Default 512 MiB constant |
| `active_request_bytes` | `active_requests * 256 KiB` |
| `total_estimated_bytes` | `max(sum of components, gpu_memory_used)` when NVML reports used memory |

Methodology string is stored on the breakdown object.

## Capacity Model

Location: `packages/observability/src/gpu_inference_observability/gpu/capacity.py`

**Inputs:** active requests (control plane), active sequences and batches (scheduler), GPU memory pressure, KV occupancy.

**`CapacitySnapshot` fields:**

- `active_requests`
- `active_sequences`
- `active_batches`
- `max_concurrent_sequences`
- `capacity_remaining = min(max_sequences - active_sequences, max_batch_slots - active_batches)`
- `limiting_resource`: `kv_cache` | `batch_slots` | `gpu_memory` | `none`

No scheduling behavior changes. Snapshot is observability only.

## Prometheus Metrics

| Metric | Type | Labels |
|--------|------|--------|
| `gpu_inference_gpu_utilization_percent` | Gauge | `device_id` |
| `gpu_inference_gpu_memory_used_bytes` | Gauge | `device_id` |
| `gpu_inference_gpu_memory_free_bytes` | Gauge | `device_id` |
| `gpu_inference_gpu_memory_total_bytes` | Gauge | `device_id` |
| `gpu_inference_kv_cache_estimated_bytes` | Gauge | — |
| `gpu_inference_active_sequences` | Gauge | — |
| `gpu_inference_capacity_remaining` | Gauge | — |

Contract names `gpu_utilization_ratio` in Session 3 docs remain catalog entries; Session 21 exports `gpu_utilization_percent` as specified.

## Capacity Events

Location: `packages/observability/src/gpu_inference_observability/gpu/events.py`

| Event | Trigger (default thresholds) |
|-------|------------------------------|
| `kv_cache_pressure_detected` | occupancy ≥ 0.85 |
| `memory_threshold_crossed` | GPU memory used ratio ≥ 0.90 |
| `gpu_capacity_warning` | GPU memory threshold or low `capacity_remaining` |
| `capacity_exhausted` | `capacity_remaining == 0` |

Events are written to structured logs and the runtime trace store. No alerting integration.

## Operator Questions

| Question | Derivation |
|----------|------------|
| How much GPU memory is used? | `gpu_memory_used_bytes{device_id}` from NVML or fallback zeros |
| How much memory is estimated KV cache? | `kv_cache_estimated_bytes` or `KVCacheMetrics.estimated_kv_bytes` |
| How many active sequences? | `active_sequences` gauge; scheduler `BatchStatistics.total_active_requests` |
| Which resource limits concurrency? | `CapacitySnapshot.limiting_resource` |
| How much capacity remains? | `capacity_remaining` gauge; `min(remaining sequence slots, remaining batch slots)` |

## Validation

`runtime-validation/gpu_validation.py` scenarios:

- Idle system
- Moderate load
- Increasing concurrency
- Cache pressure simulation
- Capacity exhaustion simulation
- Runtime path metric export

Uses `SimulatedGPUProbe`. No benchmarking.

Run: `python runtime-validation/gpu_validation.py`

## Limitations

- KV cache and model weight sizes are estimates unless backend exposes real counters (not implemented).
- NVML requires NVIDIA GPU and optional `nvidia-ml-py` dependency.
- Fallback probe returns zeros; metrics present but not hardware-backed.
- Single collection on stack startup by default; no background poll loop.
- vLLM `/metrics` endpoint is not scraped.
- Per-model memory breakdown is not implemented.

## Planned / Not Implemented

- Autoscaling from GPU telemetry
- Scheduling optimization from capacity model
- Benchmark harness
- Operator dashboard UI
- Direct vLLM KV block counter integration
