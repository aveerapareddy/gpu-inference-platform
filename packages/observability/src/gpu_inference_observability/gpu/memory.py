"""Memory accounting estimates. Owner: gpu_inference_observability.gpu."""

from __future__ import annotations

from dataclasses import dataclass

from gpu_inference_observability.gpu.models import GPUDeviceMetrics, MemoryBreakdown


@dataclass(frozen=True, slots=True)
class MemoryAccountingInputs:
    gpu_devices: tuple[GPUDeviceMetrics, ...]
    kv_cache_bytes: int
    active_requests: int
    model_weights_bytes: int = 4 * 1024 * 1024 * 1024
    runtime_overhead_bytes: int = 512 * 1024 * 1024
    bytes_per_active_request: int = 256 * 1024


def build_memory_breakdown(inputs: MemoryAccountingInputs) -> MemoryBreakdown:
    gpu_used = sum(device.memory_used_bytes for device in inputs.gpu_devices)
    active_request_bytes = max(0, inputs.active_requests) * inputs.bytes_per_active_request
    runtime_overhead = inputs.runtime_overhead_bytes
    model_weights = inputs.model_weights_bytes
    kv_cache = max(0, inputs.kv_cache_bytes)

    # When NVML reports device memory, reconcile totals against GPU used bytes.
    total_estimated = model_weights + kv_cache + runtime_overhead + active_request_bytes
    if gpu_used > 0:
        total_estimated = max(total_estimated, gpu_used)

    return MemoryBreakdown(
        model_weights_bytes=model_weights,
        kv_cache_bytes=kv_cache,
        runtime_overhead_bytes=runtime_overhead,
        active_request_bytes=active_request_bytes,
        total_estimated_bytes=total_estimated,
        methodology=(
            "model_weights + kv_cache + runtime_overhead + active_request_bytes; "
            "total_estimated=max(sum, gpu_memory_used) when NVML available"
        ),
    )
