"""Streaming metrics record. Owner: inference adapter; read by control plane."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StreamingMetricsRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    stream_id: UUID
    request_id: UUID
    ttft_ms: float | None = Field(default=None, ge=0.0)
    itl_ms_p50: float | None = Field(default=None, ge=0.0)
    itl_ms_p99: float | None = Field(default=None, ge=0.0)
    token_count: int = Field(default=0, ge=0)
    generated_text: str = ""
    completed_at: datetime | None = None
    stream_state: str
