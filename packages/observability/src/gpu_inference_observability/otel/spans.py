"""Span names for request path hierarchy. Owner: gpu_inference_observability.otel."""

from __future__ import annotations

from enum import StrEnum


class SpanName(StrEnum):
    REQUEST = "request"
    VALIDATION = "validation"
    ADMISSION = "admission"
    QUEUE = "queue"
    SCHEDULER = "scheduler"
    BATCH = "batch"
    BACKEND_SUBMISSION = "backend_submission"
    COMPLETION = "completion"


class ComponentName(StrEnum):
    GATEWAY = "gateway"
    CONTROL_PLANE = "control_plane"
    SCHEDULER = "scheduler"
    ADAPTER = "adapter"
    BACKEND = "backend"
