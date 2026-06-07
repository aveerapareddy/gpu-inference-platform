"""GPU device probes. NVML when available; fallback otherwise."""

from __future__ import annotations

from typing import Protocol

from gpu_inference_observability.gpu.models import GPUDeviceMetrics, GPUMetricsSource


class GPUProbe(Protocol):
    def collect(self) -> tuple[GPUDeviceMetrics, ...]: ...


class FallbackGPUProbe:
    """Returns zeroed metrics when no GPU telemetry is available."""

    def collect(self) -> tuple[GPUDeviceMetrics, ...]:
        return (
            GPUDeviceMetrics(
                device_id=0,
                utilization_percent=0.0,
                memory_used_bytes=0,
                memory_free_bytes=0,
                memory_total_bytes=0,
                source=GPUMetricsSource.FALLBACK,
            ),
        )


class NVMLGPUProbe:
    """Collect metrics via NVML (pynvml). Falls back on import or runtime errors."""

    def __init__(self) -> None:
        self._initialized = False
        self._device_count = 0
        self._fallback = FallbackGPUProbe()
        self._init_error: str | None = None
        try:
            import pynvml  # type: ignore[import-untyped]

            pynvml.nvmlInit()
            self._device_count = pynvml.nvmlDeviceGetCount()
            self._pynvml = pynvml
            self._initialized = True
        except Exception as exc:
            self._init_error = str(exc)

    def collect(self) -> tuple[GPUDeviceMetrics, ...]:
        if not self._initialized:
            return self._fallback.collect()
        results: list[GPUDeviceMetrics] = []
        try:
            for index in range(self._device_count):
                handle = self._pynvml.nvmlDeviceGetHandleByIndex(index)
                util = self._pynvml.nvmlDeviceGetUtilizationRates(handle)
                mem = self._pynvml.nvmlDeviceGetMemoryInfo(handle)
                results.append(
                    GPUDeviceMetrics(
                        device_id=index,
                        utilization_percent=float(util.gpu),
                        memory_used_bytes=int(mem.used),
                        memory_free_bytes=int(mem.free),
                        memory_total_bytes=int(mem.total),
                        source=GPUMetricsSource.NVML,
                    )
                )
        except Exception:
            return self._fallback.collect()
        return tuple(results) if results else self._fallback.collect()


class SimulatedGPUProbe:
    """Deterministic probe for validation without hardware."""

    def __init__(self) -> None:
        self._utilization = 0.0
        self._memory_used = 0
        self._memory_total = 16 * 1024 * 1024 * 1024

    def set_state(
        self,
        *,
        utilization_percent: float,
        memory_used_bytes: int,
        memory_total_bytes: int | None = None,
    ) -> None:
        self._utilization = utilization_percent
        self._memory_used = memory_used_bytes
        if memory_total_bytes is not None:
            self._memory_total = memory_total_bytes

    def collect(self) -> tuple[GPUDeviceMetrics, ...]:
        free = max(0, self._memory_total - self._memory_used)
        return (
            GPUDeviceMetrics(
                device_id=0,
                utilization_percent=self._utilization,
                memory_used_bytes=self._memory_used,
                memory_free_bytes=free,
                memory_total_bytes=self._memory_total,
                source=GPUMetricsSource.SIMULATED,
            ),
        )


def create_gpu_probe(*, simulated: GPUProbe | None = None) -> GPUProbe:
    if simulated is not None:
        return simulated
    probe = NVMLGPUProbe()
    sample = probe.collect()
    if sample and sample[0].source == GPUMetricsSource.NVML:
        return probe
    return FallbackGPUProbe()
