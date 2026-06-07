"""GPU metrics collector. Owner: gpu_inference_observability.gpu."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from gpu_inference_observability.gpu.capacity import CapacityInputs, build_capacity_snapshot
from gpu_inference_observability.gpu.events import CapacityEventEmitter, CapacityEventType
from gpu_inference_observability.gpu.kv_cache import KVCacheInputs, estimate_kv_cache_metrics
from gpu_inference_observability.gpu.memory import MemoryAccountingInputs, build_memory_breakdown
from gpu_inference_observability.gpu.models import GPUObservabilitySnapshot
from gpu_inference_observability.gpu.probes import GPUProbe, create_gpu_probe
from gpu_inference_observability.registry.recorder import RuntimeMetricsRecorder


class RuntimeContextProvider(Protocol):
    def active_requests(self) -> int: ...
    def active_sequences(self) -> int: ...
    def active_batches(self) -> int: ...
    def max_concurrent_sequences(self) -> int: ...
    def max_batch_slots(self) -> int: ...


@dataclass
class GPUCollectorConfig:
    kv_cache_pressure_ratio: float = 0.85
    gpu_memory_threshold_ratio: float = 0.90
    capacity_warning_remaining: int = 2


class GPUMetricsCollector:
    """Collects GPU, KV cache, memory, and capacity telemetry."""

    def __init__(
        self,
        *,
        metrics_recorder: RuntimeMetricsRecorder | None = None,
        context_provider: RuntimeContextProvider | None = None,
        events: CapacityEventEmitter | None = None,
        probe: GPUProbe | None = None,
        config: GPUCollectorConfig | None = None,
    ) -> None:
        self._metrics = metrics_recorder
        self._context = context_provider
        self._events = events
        self._probe = probe if probe is not None else create_gpu_probe()
        self._config = config or GPUCollectorConfig()
        self._last_kv_pressure = False
        self._last_gpu_pressure = False
        self._last_capacity_exhausted = False

    def collect(self) -> GPUObservabilitySnapshot:
        devices = self._probe.collect()
        active_requests = self._context.active_requests() if self._context else 0
        active_sequences = self._context.active_sequences() if self._context else 0
        active_batches = self._context.active_batches() if self._context else 0
        max_sequences = self._context.max_concurrent_sequences() if self._context else 32
        max_batch_slots = self._context.max_batch_slots() if self._context else 32

        kv_cache = estimate_kv_cache_metrics(
            KVCacheInputs(
                active_sequences=active_sequences,
                max_concurrent_sequences=max_sequences,
            )
        )
        memory = build_memory_breakdown(
            MemoryAccountingInputs(
                gpu_devices=devices,
                kv_cache_bytes=kv_cache.estimated_kv_bytes,
                active_requests=active_requests,
            )
        )
        capacity = build_capacity_snapshot(
            CapacityInputs(
                active_requests=active_requests,
                active_sequences=active_sequences,
                active_batches=active_batches,
                max_concurrent_sequences=max_sequences,
                kv_cache=kv_cache,
                gpu_devices=devices,
                max_batch_slots=max_batch_slots,
            )
        )

        self._export_metrics(devices, kv_cache, capacity)
        self._emit_threshold_events(devices, kv_cache, capacity, memory)

        return GPUObservabilitySnapshot(
            devices=devices,
            kv_cache=kv_cache,
            memory=memory,
            capacity=capacity,
        )

    def _export_metrics(self, devices, kv_cache, capacity) -> None:
        if self._metrics is None:
            return
        for device in devices:
            self._metrics.set_gpu_device_metrics(
                device_id=str(device.device_id),
                utilization_percent=device.utilization_percent,
                memory_used_bytes=device.memory_used_bytes,
                memory_free_bytes=device.memory_free_bytes,
                memory_total_bytes=device.memory_total_bytes,
            )
        self._metrics.set_kv_cache_estimated_bytes(kv_cache.estimated_kv_bytes)
        self._metrics.set_active_sequences(kv_cache.active_sequences)
        self._metrics.set_capacity_remaining(capacity.capacity_remaining)

    def _emit_threshold_events(self, devices, kv_cache, capacity, memory) -> None:
        if self._events is None:
            return

        kv_pressure = kv_cache.cache_occupancy_ratio >= self._config.kv_cache_pressure_ratio
        if kv_pressure and not self._last_kv_pressure:
            self._events.emit(
                CapacityEventType.KV_CACHE_PRESSURE_DETECTED,
                extra={
                    "occupancy_ratio": kv_cache.cache_occupancy_ratio,
                    "active_sequences": kv_cache.active_sequences,
                },
            )
        self._last_kv_pressure = kv_pressure

        gpu_pressure = False
        if devices:
            device = devices[0]
            if device.memory_total_bytes > 0:
                ratio = device.memory_used_bytes / device.memory_total_bytes
                gpu_pressure = ratio >= self._config.gpu_memory_threshold_ratio
                if gpu_pressure and not self._last_gpu_pressure:
                    self._events.emit(
                        CapacityEventType.MEMORY_THRESHOLD_CROSSED,
                        extra={
                            "memory_used_bytes": device.memory_used_bytes,
                            "memory_total_bytes": device.memory_total_bytes,
                            "threshold_ratio": self._config.gpu_memory_threshold_ratio,
                        },
                    )
                    self._events.emit(
                        CapacityEventType.GPU_CAPACITY_WARNING,
                        extra={"utilization_percent": device.utilization_percent},
                    )
        self._last_gpu_pressure = gpu_pressure

        exhausted = capacity.capacity_remaining <= 0
        if exhausted and not self._last_capacity_exhausted:
            self._events.emit(
                CapacityEventType.CAPACITY_EXHAUSTED,
                extra={
                    "limiting_resource": capacity.limiting_resource,
                    "active_sequences": capacity.active_sequences,
                },
            )
        elif (
            not exhausted
            and capacity.capacity_remaining <= self._config.capacity_warning_remaining
            and capacity.limiting_resource != "none"
        ):
            self._events.emit(
                CapacityEventType.GPU_CAPACITY_WARNING,
                extra={
                    "capacity_remaining": capacity.capacity_remaining,
                    "limiting_resource": capacity.limiting_resource,
                },
            )
        self._last_capacity_exhausted = exhausted
