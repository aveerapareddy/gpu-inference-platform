"""Trace context scaffolding.

Status: Implemented (Session 3). Header contract only; no OpenTelemetry SDK.
Runtime spans: gpu_inference_observability.otel (Session 14).
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class TraceSpanName(StrEnum):
    """Span names fixed by Session 1 observability contract."""

    GATEWAY_RECEIVE = "gateway.receive"
    GATEWAY_VALIDATE = "gateway.validate"
    GATEWAY_STREAM = "gateway.stream"
    CONTROL_PLANE_RESOLVE_MODEL = "control_plane.resolve_model"
    SCHEDULER_ADMIT = "scheduler.admit"
    SCHEDULER_QUEUE_WAIT = "scheduler.queue_wait"
    SCHEDULER_DISPATCH = "scheduler.dispatch"
    ADAPTER_PREFILL = "adapter.prefill"
    ADAPTER_DECODE = "adapter.decode"


@dataclass(frozen=True, slots=True)
class TraceContext:
    """Correlation identifiers propagated on internal calls."""

    trace_id: str
    span_id: str
    request_id: UUID
    parent_span_id: str | None = None

    @staticmethod
    def new_trace(request_id: UUID) -> TraceContext:
        return TraceContext(
            trace_id=secrets.token_hex(16),
            span_id=secrets.token_hex(8),
            request_id=request_id,
        )

    def child_span(self) -> TraceContext:
        return TraceContext(
            trace_id=self.trace_id,
            span_id=secrets.token_hex(8),
            request_id=self.request_id,
            parent_span_id=self.span_id,
        )

    def as_headers(self) -> dict[str, str]:
        """Header map for internal HTTP propagation (planned)."""
        headers = {
            "X-Trace-Id": self.trace_id,
            "X-Span-Id": self.span_id,
            "X-Request-Id": str(self.request_id),
        }
        if self.parent_span_id is not None:
            headers["X-Parent-Span-Id"] = self.parent_span_id
        return headers
