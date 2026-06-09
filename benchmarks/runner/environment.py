"""Benchmark environment capture. Owner: benchmarks.runner."""

from __future__ import annotations

import importlib.util
import os
import platform
import socket
import sys
from datetime import datetime, timezone

from benchmarks.runner.models import BenchmarkEnvironment, HardwareMetadata, ModelMetadata

try:
    import psutil
except ImportError:  # pragma: no cover
    psutil = None


def detect_vllm_version() -> str | None:
    if importlib.util.find_spec("vllm") is None:
        return None
    try:
        import vllm

        return getattr(vllm, "__version__", None)
    except Exception:
        return None


def _capture_gpu_fields() -> tuple[str | None, int | None, int, str]:
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
    return gpu_model, gpu_memory_total, gpu_count, gpu_source


def capture_hardware_metadata() -> HardwareMetadata:
    ram_bytes = psutil.virtual_memory().total if psutil is not None else None
    gpu_model, gpu_memory_total, gpu_count, gpu_source = _capture_gpu_fields()
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
        os_name=platform.system(),
        os_version=platform.release(),
    )


def capture_model_metadata(
    *,
    model_id: str = "demo",
    backend_id: str = "mock",
    stream: bool = False,
) -> ModelMetadata:
    model_size = os.environ.get("BENCHMARK_MODEL_SIZE")
    vllm_version = detect_vllm_version()
    return ModelMetadata(
        model_id=model_id,
        backend_id=backend_id,
        max_output_tokens=None,
        stream=stream,
        model_size=model_size,
        vllm_version=vllm_version,
        configuration={
            "source": "benchmark_runner",
            "model_name": model_id,
        },
    )


def capture_benchmark_environment(
    *,
    model_id: str = "demo",
    backend_id: str = "mock",
    stream: bool = False,
) -> BenchmarkEnvironment:
    hardware = capture_hardware_metadata()
    model = capture_model_metadata(model_id=model_id, backend_id=backend_id, stream=stream)
    return BenchmarkEnvironment(
        gpu_model=hardware.gpu_model,
        gpu_memory_total_bytes=hardware.gpu_memory_total_bytes,
        gpu_count=hardware.gpu_count,
        gpu_source=hardware.gpu_source,
        cpu_model=hardware.cpu_model,
        ram_bytes=hardware.ram_bytes,
        os=f"{hardware.os_name} {hardware.os_version}".strip(),
        platform=hardware.platform,
        python_version=hardware.python_version,
        vllm_version=model.vllm_version,
        model_name=model.model_id,
        model_size=model.model_size,
        backend_id=model.backend_id or backend_id,
        hostname=hardware.hostname,
        captured_at=datetime.now(timezone.utc),
    )
