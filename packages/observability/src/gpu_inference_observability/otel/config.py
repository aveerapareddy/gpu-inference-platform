"""Trace export configuration. No collector deployment."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class TraceExporterType(StrEnum):
    NONE = "none"
    CONSOLE = "console"
    OTLP = "otlp"
    MEMORY = "memory"


@dataclass(frozen=True, slots=True)
class TraceExportConfig:
    """Pluggable exporter configuration."""

    exporter: TraceExporterType = TraceExporterType.MEMORY
    service_name: str = "gpu-inference-platform"
    otlp_endpoint: str = "http://localhost:4318/v1/traces"
