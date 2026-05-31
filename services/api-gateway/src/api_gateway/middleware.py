"""Request timing and access logging."""

from __future__ import annotations

import time

from fastapi import Request, Response
from gpu_inference_observability import LogContext, StructuredLogger
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from api_gateway.config import Settings


class RequestTimingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, settings: Settings, logger: StructuredLogger) -> None:
        super().__init__(app)
        self._settings = settings
        self._logger = logger

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        started = time.perf_counter()
        correlation_id = (
            request.headers.get("X-Correlation-Id")
            or request.headers.get("X-Request-Id")
            or ""
        )
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        log_ctx = LogContext(
            service=self._settings.service_name,
            trace_id=correlation_id or None,
        )
        self._logger.info(
            "request completed",
            ctx=log_ctx,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(elapsed_ms, 3),
        )
        if correlation_id:
            response.headers["X-Correlation-Id"] = correlation_id
        return response
