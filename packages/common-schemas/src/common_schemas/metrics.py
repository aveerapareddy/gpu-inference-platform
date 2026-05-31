"""Per-request observability record types."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from common_schemas.states import FailureReason, PriorityClass, TerminalStatus


class RequestMetrics(BaseModel):
    """Merged at terminal. Owner: all services; metrics collector aggregates."""

    model_config = ConfigDict(extra="forbid", strict=True)

    request_id: UUID
    model: str
    status: TerminalStatus
    failure_reason: FailureReason | None
    arrival_time: datetime
    backend: str | None = None
    queue_wait_ms: int | None = Field(default=None, ge=0)
    scheduling_ms: int | None = Field(default=None, ge=0)
    ttft_ms: int | None = Field(default=None, ge=0)
    itl_ms_p50: float | None = Field(default=None, ge=0.0)
    itl_ms_p99: float | None = Field(default=None, ge=0.0)
    completion_ms: int | None = Field(default=None, ge=0)
    token_count: int | None = Field(default=None, ge=0)
    worker_id: str | None = None
    batch_id: UUID | None = None
    stream: bool | None = None
    priority_class: PriorityClass | None = None
