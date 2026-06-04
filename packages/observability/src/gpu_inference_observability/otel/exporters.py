"""Span exporters for tests and runtime configuration."""

from __future__ import annotations

from opentelemetry.sdk.trace.export import ReadableSpan, SpanExporter, SpanExportResult


class InMemorySpanExporter(SpanExporter):
    """Collects exported spans for validation. Not for production use."""

    def __init__(self) -> None:
        self.spans: list[ReadableSpan] = []

    def export(self, spans: list[ReadableSpan]) -> SpanExportResult:
        self.spans.extend(spans)
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        return None

    def clear(self) -> None:
        self.spans.clear()

    def get_finished_spans(self) -> list[ReadableSpan]:
        return list(self.spans)
