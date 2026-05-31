"""Structured logging scaffolding.

Status: Implemented (Session 3). Emits dict records; no log shipper integration.
"""

from __future__ import annotations

import json
import logging
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID


@dataclass(frozen=True, slots=True)
class LogContext:
    """Fields required on every log line."""

    service: str
    request_id: UUID | None = None
    trace_id: str | None = None
    span_id: str | None = None
    model: str | None = None
    batch_id: UUID | None = None
    worker_id: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def with_fields(self, **kwargs: Any) -> LogContext:
        data = asdict(self)
        extra = dict(data.pop("extra", {}))
        for key, value in kwargs.items():
            if key in ("service", "request_id", "trace_id", "span_id", "model", "batch_id", "worker_id"):
                data[key] = value
            else:
                extra[key] = value
        data["extra"] = extra
        return LogContext(**data)


class StructuredLogger:
    """JSON-per-line logger using stdlib logging as transport."""

    def __init__(self, service: str, level: int = logging.INFO) -> None:
        self._service = service
        self._logger = logging.getLogger(f"gpu_inference.{service}")
        self._logger.setLevel(level)
        if not self._logger.handlers:
            handler = logging.StreamHandler(sys.stderr)
            handler.setFormatter(logging.Formatter("%(message)s"))
            self._logger.addHandler(handler)

    def base_context(self) -> LogContext:
        return LogContext(service=self._service)

    def log(
        self,
        level: int,
        message: str,
        ctx: LogContext | None = None,
        **fields: Any,
    ) -> None:
        ctx = ctx or self.base_context()
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": logging.getLevelName(level),
            "service": ctx.service,
            "message": message,
        }
        if ctx.request_id is not None:
            record["request_id"] = str(ctx.request_id)
        if ctx.trace_id is not None:
            record["trace_id"] = ctx.trace_id
        if ctx.span_id is not None:
            record["span_id"] = ctx.span_id
        if ctx.model is not None:
            record["model"] = ctx.model
        if ctx.batch_id is not None:
            record["batch_id"] = str(ctx.batch_id)
        if ctx.worker_id is not None:
            record["worker_id"] = ctx.worker_id
        if ctx.extra:
            record.update(ctx.extra)
        record.update(fields)
        self._logger.log(level, json.dumps(record, default=str))

    def info(self, message: str, ctx: LogContext | None = None, **fields: Any) -> None:
        self.log(logging.INFO, message, ctx, **fields)

    def warning(self, message: str, ctx: LogContext | None = None, **fields: Any) -> None:
        self.log(logging.WARNING, message, ctx, **fields)

    def error(self, message: str, ctx: LogContext | None = None, **fields: Any) -> None:
        self.log(logging.ERROR, message, ctx, **fields)
