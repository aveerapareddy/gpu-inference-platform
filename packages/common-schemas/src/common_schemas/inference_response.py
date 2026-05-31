"""Inference response and streaming types."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from common_schemas.states import FinishReason


class TokenUsage(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)


class AssistantMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    role: str = "assistant"
    content: str


class Choice(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    message: AssistantMessage
    finish_reason: FinishReason


class InferenceResponse(BaseModel):
    """Non-streaming completion envelope. Owner: scheduler to gateway."""

    model_config = ConfigDict(extra="forbid", strict=True)

    request_id: UUID
    model: str
    choices: list[Choice] = Field(min_length=1, max_length=1)
    usage: TokenUsage | None = None
    finish_reason: FinishReason


class StreamingChunk(BaseModel):
    """Incremental token from adapter."""

    model_config = ConfigDict(extra="forbid", strict=True)

    request_id: UUID
    batch_id: UUID
    index: int = Field(ge=0)
    delta_text: str
    finish_reason: FinishReason | None
    created_at: datetime


class CompletionResult(BaseModel):
    """Terminal success payload. Owner: inference adapter."""

    model_config = ConfigDict(extra="forbid", strict=True)

    request_id: UUID
    status: str = "completed"
    finish_reason: FinishReason
    usage: TokenUsage | None = None
    completed_at: datetime
