"""Optional span helpers for components without a configured TraceManager."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from gpu_inference_observability.otel.manager import TraceManager
from gpu_inference_observability.otel.scope import SpanScope


class _NoOpSpanScope:
    def set_request_context(self, **kwargs: Any) -> None:
        return None

    def set_attribute(self, key: str, value: Any) -> None:
        return None

    def record_exception(self, exc: BaseException) -> None:
        return None

    def record_failure(self, failure_type: str, reason: str) -> None:
        return None

    def record_rejection(self, reason: str, *, failure_type: str = "rejected") -> None:
        return None

    def record_timeout(self, reason: str) -> None:
        return None


@contextmanager
def optional_span(
    manager: TraceManager | None,
    *args: Any,
    **kwargs: Any,
) -> Iterator[SpanScope | _NoOpSpanScope]:
    if manager is None:
        yield _NoOpSpanScope()
        return
    with manager.span(*args, **kwargs) as scope:
        yield scope
