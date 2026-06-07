"""Inference completion record. Owner: inference adapter; read by control plane."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class InferenceCompletionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    request_id: UUID
    backend_id: str
    generated_text: str
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    finish_reason: str | None = None
    completed_at: datetime
    execution_duration_ms: float | None = Field(default=None, ge=0.0)
