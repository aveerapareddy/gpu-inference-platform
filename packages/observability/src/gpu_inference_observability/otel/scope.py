"""Active span wrapper with error instrumentation."""

from __future__ import annotations

from opentelemetry.trace import Span, Status, StatusCode

from gpu_inference_observability.otel.attributes import SpanAttributes


class SpanScope:
    """Wraps an OpenTelemetry span with platform attribute helpers."""

    def __init__(self, span: Span) -> None:
        self._span = span

    @property
    def span(self) -> Span:
        return self._span

    def set_request_context(
        self,
        *,
        request_id: UUID | str | None = None,
        correlation_id: str | None = None,
        batch_id: UUID | str | None = None,
        backend_id: str | None = None,
        request_state: str | None = None,
        batch_state: str | None = None,
        component_name: str | None = None,
        model: str | None = None,
    ) -> None:
        mapping: dict[str, Any] = {
            SpanAttributes.REQUEST_ID: str(request_id) if request_id is not None else None,
            SpanAttributes.CORRELATION_ID: correlation_id,
            SpanAttributes.BATCH_ID: str(batch_id) if batch_id is not None else None,
            SpanAttributes.BACKEND_ID: backend_id,
            SpanAttributes.REQUEST_STATE: request_state,
            SpanAttributes.BATCH_STATE: batch_state,
            SpanAttributes.COMPONENT_NAME: component_name,
            SpanAttributes.MODEL: model,
        }
        for key, value in mapping.items():
            if value is not None:
                self._span.set_attribute(key, value)

    def set_attribute(self, key: str, value: Any) -> None:
        if value is not None:
            self._span.set_attribute(key, value)

    def record_exception(self, exc: BaseException) -> None:
        self._span.record_exception(exc)
        self._span.set_status(Status(StatusCode.ERROR, str(exc)))

    def record_failure(self, failure_type: str, reason: str) -> None:
        self._span.set_attribute(SpanAttributes.FAILURE_TYPE, failure_type)
        self._span.set_attribute(SpanAttributes.FAILURE_REASON, reason)
        self._span.add_event(
            "failure",
            attributes={
                SpanAttributes.FAILURE_TYPE: failure_type,
                SpanAttributes.FAILURE_REASON: reason,
            },
        )
        self._span.set_status(Status(StatusCode.ERROR, reason))

    def record_rejection(self, reason: str, *, failure_type: str = "rejected") -> None:
        self.record_failure(failure_type, reason)

    def record_timeout(self, reason: str) -> None:
        self.record_failure("timeout", reason)

    def end(self) -> None:
        self._span.end()
