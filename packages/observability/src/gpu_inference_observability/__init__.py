"""Observability scaffolding. No Prometheus or OpenTelemetry integration yet."""

from gpu_inference_observability.logging import LogContext, StructuredLogger
from gpu_inference_observability.metrics import MetricKind, MetricName, prometheus_name
from gpu_inference_observability.tracing import TraceContext, TraceSpanName

__all__ = [
    "LogContext",
    "MetricKind",
    "MetricName",
    "prometheus_name",
    "StructuredLogger",
    "TraceContext",
    "TraceSpanName",
]

__version__ = "0.1.0"
