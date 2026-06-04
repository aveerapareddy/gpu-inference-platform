"""Helpers for validating exported OpenTelemetry spans."""

from __future__ import annotations

from opentelemetry.sdk.trace.export import ReadableSpan

from gpu_inference_observability.otel.attributes import SpanAttributes
from gpu_inference_observability.otel.exporters import InMemorySpanExporter


class TraceSpanInspector:
    def __init__(self, exporter: InMemorySpanExporter) -> None:
        self._exporter = exporter

    def finished_spans(self) -> list[ReadableSpan]:
        return self._exporter.get_finished_spans()

    def spans_named(self, name: str) -> list[ReadableSpan]:
        return [span for span in self.finished_spans() if span.name == name]

    def span_attributes(self, span: ReadableSpan) -> dict:
        return dict(span.attributes or {})

    def parent_span_id(self, span: ReadableSpan) -> int | None:
        if span.parent is None:
            return None
        return span.parent.span_id

    def trace_ids(self) -> set[int]:
        return {span.context.trace_id for span in self.finished_spans()}

    def assert_single_trace(self) -> int:
        trace_ids = self.trace_ids()
        assert len(trace_ids) == 1, f"expected one trace, got {len(trace_ids)}"
        return next(iter(trace_ids))

    def assert_parent_child(self, parent: ReadableSpan, child: ReadableSpan) -> None:
        assert child.parent is not None, f"child span {child.name} has no parent"
        assert child.parent.span_id == parent.context.span_id, (
            f"{child.name} parent mismatch: expected {parent.context.span_id}, "
            f"got {child.parent.span_id}"
        )

    def assert_attribute(self, span: ReadableSpan, key: str, expected: str) -> None:
        attrs = self.span_attributes(span)
        assert key in attrs, f"{span.name} missing attribute {key}"
        assert str(attrs[key]) == expected, f"{span.name}.{key}={attrs[key]!r}, expected {expected!r}"

    def assert_request_attributes(
        self,
        span: ReadableSpan,
        *,
        request_id: str,
        correlation_id: str,
    ) -> None:
        self.assert_attribute(span, SpanAttributes.REQUEST_ID, request_id)
        self.assert_attribute(span, SpanAttributes.CORRELATION_ID, correlation_id)
