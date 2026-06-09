"""Hardware and model metadata capture. Owner: benchmarks.runner."""

from __future__ import annotations

import platform
import socket
import sys

from benchmarks.runner.models import HardwareMetadata, ModelMetadata

try:
    import psutil
except ImportError:  # pragma: no cover - optional for validation
    psutil = None


def capture_hardware_metadata() -> HardwareMetadata:
    ram_bytes = None
    if psutil is not None:
        ram_bytes = psutil.virtual_memory().total

    gpu_model = None
    gpu_memory_total = None
    gpu_count = 0
    gpu_source = "unavailable"

    try:
        from gpu_inference_observability.gpu.probes import create_gpu_probe

        devices = create_gpu_probe().collect()
        if devices:
            gpu_count = len(devices)
            primary = devices[0]
            gpu_memory_total = primary.memory_total_bytes
            gpu_source = primary.source.value
            if primary.memory_total_bytes > 0:
                gpu_model = f"device_{primary.device_id}"
    except Exception:
        pass

    return HardwareMetadata(
        platform=platform.platform(),
        python_version=sys.version.split()[0],
        cpu_model=platform.processor() or platform.machine(),
        ram_bytes=ram_bytes,
        gpu_model=gpu_model,
        gpu_memory_total_bytes=gpu_memory_total,
        gpu_count=gpu_count,
        gpu_source=gpu_source,
        hostname=socket.gethostname(),
    )


def capture_model_metadata(*, model_id: str = "demo", backend_id: str = "mock", stream: bool = False) -> ModelMetadata:
    return ModelMetadata(
        model_id=model_id,
        backend_id=backend_id,
        max_output_tokens=None,
        stream=stream,
        configuration={"source": "benchmark_runner"},
    )
