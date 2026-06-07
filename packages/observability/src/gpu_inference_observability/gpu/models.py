"""GPU observability domain models. Owner: gpu_inference_observability.gpu."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum


class GPUMetricsSource(StrEnum):
    NVML = "nvml"
    FALLBACK = "fallback_unavailable"
    SIMULATED = "simulated"


@dataclass(frozen=True, slots=True)
class GPUDeviceMetrics:
    device_id: int
    utilization_percent: float
    memory_used_bytes: int
    memory_free_bytes: int
    memory_total_bytes: int
    source: GPUMetricsSource


@dataclass(frozen=True, slots=True)
class KVCacheMetrics:
    """Estimated KV cache state. Values are estimates unless backend exposes real counters."""

    cache_entries: int
    active_sequences: int
    cache_occupancy_ratio: float
    estimated_kv_bytes: int
    estimation_method: str
    bytes_per_sequence: int


@dataclass(frozen=True, slots=True)
class MemoryBreakdown:
    """Structured memory accounting. All fields are estimates derived from runtime inputs."""

    model_weights_bytes: int
    kv_cache_bytes: int
    runtime_overhead_bytes: int
    active_request_bytes: int
    total_estimated_bytes: int
    methodology: str


@dataclass(frozen=True, slots=True)
class CapacitySnapshot:
    active_requests: int
    active_sequences: int
    active_batches: int
    max_concurrent_sequences: int
    capacity_remaining: int
    limiting_resource: str
    captured_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class GPUObservabilitySnapshot:
    devices: tuple[GPUDeviceMetrics, ...]
    kv_cache: KVCacheMetrics
    memory: MemoryBreakdown
    capacity: CapacitySnapshot
    captured_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
