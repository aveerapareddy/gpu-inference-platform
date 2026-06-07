"""Capacity model. Owner: gpu_inference_observability.gpu."""

from __future__ import annotations

from dataclasses import dataclass

from gpu_inference_observability.gpu.models import CapacitySnapshot, GPUDeviceMetrics, KVCacheMetrics


@dataclass(frozen=True, slots=True)
class CapacityInputs:
    active_requests: int
    active_sequences: int
    active_batches: int
    max_concurrent_sequences: int
    kv_cache: KVCacheMetrics
    gpu_devices: tuple[GPUDeviceMetrics, ...]
    max_batch_slots: int = 32


def build_capacity_snapshot(inputs: CapacityInputs) -> CapacitySnapshot:
    remaining_sequences = max(0, inputs.max_concurrent_sequences - inputs.active_sequences)
    remaining_batch = max(0, inputs.max_batch_slots - inputs.active_batches)
    capacity_remaining = min(remaining_sequences, remaining_batch)

    gpu_device = inputs.gpu_devices[0] if inputs.gpu_devices else None
    gpu_pressure = False
    if gpu_device is not None and gpu_device.memory_total_bytes > 0:
        used_ratio = gpu_device.memory_used_bytes / gpu_device.memory_total_bytes
        gpu_pressure = used_ratio >= 0.9

    kv_pressure = inputs.kv_cache.cache_occupancy_ratio >= 0.85
    batch_pressure = remaining_batch <= 0
    sequence_pressure = remaining_sequences <= 0

    if sequence_pressure or kv_pressure:
        limiting = "kv_cache"
    elif batch_pressure:
        limiting = "batch_slots"
    elif gpu_pressure:
        limiting = "gpu_memory"
    else:
        limiting = "none"

    return CapacitySnapshot(
        active_requests=max(0, inputs.active_requests),
        active_sequences=max(0, inputs.active_sequences),
        active_batches=max(0, inputs.active_batches),
        max_concurrent_sequences=max(1, inputs.max_concurrent_sequences),
        capacity_remaining=capacity_remaining,
        limiting_resource=limiting,
    )
