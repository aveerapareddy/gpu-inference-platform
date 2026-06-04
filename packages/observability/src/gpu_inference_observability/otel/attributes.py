"""Standard OpenTelemetry span attributes. Owner: gpu_inference_observability.otel."""

from __future__ import annotations


class SpanAttributes:
    REQUEST_ID = "request_id"
    CORRELATION_ID = "correlation_id"
    BATCH_ID = "batch_id"
    BACKEND_ID = "backend_id"
    REQUEST_STATE = "request_state"
    BATCH_STATE = "batch_state"
    FAILURE_TYPE = "failure_type"
    COMPONENT_NAME = "component_name"
    FAILURE_REASON = "failure_reason"
    MODEL = "model"
