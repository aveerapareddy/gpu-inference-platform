"""OpenTelemetry trace manager. Backend-independent tracing abstraction."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, ClassVar, Iterator
from uuid import UUID

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter, SimpleSpanProcessor

from gpu_inference_observability.otel.attributes import SpanAttributes
from gpu_inference_observability.otel.config import TraceExportConfig, TraceExporterType
from gpu_inference_observability.otel.exporters import InMemorySpanExporter
from gpu_inference_observability.otel.scope import SpanScope
from gpu_inference_observability.otel.spans import ComponentName, SpanName


class TraceManager:
    """Creates spans, propagates context, configures exporters.

    OpenTelemetry allows one global TracerProvider per process. All instances
    share that provider and, when configured for memory export, one collector.
    """

    _shared_provider: ClassVar[TracerProvider | None] = None
    _shared_memory_exporter: ClassVar[InMemorySpanExporter | None] = None

    def __init__(self, config: TraceExportConfig | None = None) -> None:
        self._config = config or TraceExportConfig()
        if TraceManager._shared_provider is None:
            TraceManager._shared_provider = TracerProvider(
                resource=Resource.create({"service.name": self._config.service_name})
            )
            trace.set_tracer_provider(TraceManager._shared_provider)
            self._configure_exporter(TraceManager._shared_provider, self._config)
        self._provider = TraceManager._shared_provider
        self._memory_exporter = TraceManager._shared_memory_exporter
        self._tracer = trace.get_tracer("gpu_inference_observability.otel")

    @property
    def memory_exporter(self) -> InMemorySpanExporter | None:
        return self._memory_exporter

    @classmethod
    def clear_collected_spans(cls) -> None:
        """Reset in-memory spans between validation scenarios."""
        if cls._shared_memory_exporter is not None:
            cls._shared_memory_exporter.clear()

    def shutdown(self) -> None:
        self._provider.shutdown()

    def force_flush(self) -> None:
        self._provider.force_flush()

    @contextmanager
    def span(
        self,
        name: str | SpanName,
        *,
        component: str | ComponentName,
        request_id: UUID | str | None = None,
        correlation_id: str | None = None,
        batch_id: UUID | str | None = None,
        backend_id: str | None = None,
        request_state: str | None = None,
        batch_state: str | None = None,
        model: str | None = None,
        extra_attributes: dict[str, Any] | None = None,
    ) -> Iterator[SpanScope]:
        span_name = name.value if isinstance(name, SpanName) else name
        attributes: dict[str, Any] = {SpanAttributes.COMPONENT_NAME: str(component)}
        if request_id is not None:
            attributes[SpanAttributes.REQUEST_ID] = str(request_id)
        if correlation_id is not None:
            attributes[SpanAttributes.CORRELATION_ID] = correlation_id
        if batch_id is not None:
            attributes[SpanAttributes.BATCH_ID] = str(batch_id)
        if backend_id is not None:
            attributes[SpanAttributes.BACKEND_ID] = backend_id
        if request_state is not None:
            attributes[SpanAttributes.REQUEST_STATE] = request_state
        if batch_state is not None:
            attributes[SpanAttributes.BATCH_STATE] = batch_state
        if model is not None:
            attributes[SpanAttributes.MODEL] = model
        if extra_attributes:
            attributes.update(extra_attributes)

        with self._tracer.start_as_current_span(span_name, attributes=attributes) as otel_span:
            scope = SpanScope(otel_span)
            try:
                yield scope
            except BaseException as exc:
                scope.record_exception(exc)
                raise

    @classmethod
    def _configure_exporter(cls, provider: TracerProvider, config: TraceExportConfig) -> None:
        exporter_type = config.exporter
        if exporter_type == TraceExporterType.NONE:
            return
        if exporter_type == TraceExporterType.MEMORY:
            cls._shared_memory_exporter = InMemorySpanExporter()
            provider.add_span_processor(SimpleSpanProcessor(cls._shared_memory_exporter))
            return
        if exporter_type == TraceExporterType.CONSOLE:
            provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
            return
        if exporter_type == TraceExporterType.OTLP:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

            otlp_exporter = OTLPSpanExporter(endpoint=config.otlp_endpoint)
            provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
