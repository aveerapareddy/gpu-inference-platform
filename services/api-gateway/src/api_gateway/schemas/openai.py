"""Client-facing OpenAI request shapes (validation layer)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from common_schemas.states import MessageRole

ALLOWED_CHAT_FIELDS = frozenset(
    {"model", "messages", "stream", "max_tokens", "temperature", "top_p"}
)

UNSUPPORTED_CHAT_FIELDS = frozenset(
    {
        "tools",
        "tool_choice",
        "functions",
        "function_call",
        "response_format",
        "logprobs",
        "top_logprobs",
        "n",
        "presence_penalty",
        "frequency_penalty",
        "seed",
        "user",
        "stream_options",
        "parallel_tool_calls",
        "suffix",
        "echo",
        "best_of",
        "logit_bias",
        "stop",
    }
)

ALLOWED_COMPLETION_FIELDS = frozenset(
    {"model", "prompt", "stream", "max_tokens", "temperature", "top_p"}
)


class ChatMessageIn(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    role: MessageRole
    content: str

    @field_validator("role", mode="before")
    @classmethod
    def coerce_role(cls, value: object) -> MessageRole:
        if isinstance(value, MessageRole):
            return value
        if isinstance(value, str):
            return MessageRole(value)
        raise ValueError("role must be a string enum value")


class ChatCompletionRequestIn(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    model: str = Field(min_length=1)
    messages: list[ChatMessageIn] = Field(min_length=1, max_length=128)
    stream: bool = False
    max_tokens: int | None = Field(default=None, ge=1, le=32768)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)


class CompletionRequestIn(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    model: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    stream: bool = False
    max_tokens: int | None = Field(default=None, ge=1, le=32768)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)

    @field_validator("prompt")
    @classmethod
    def prompt_non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("prompt must not be empty")
        return value


def check_unsupported_fields(body: dict[str, Any], allowed: frozenset[str]) -> None:
    from api_gateway.errors import unsupported_field

    for key in body:
        if key in UNSUPPORTED_CHAT_FIELDS:
            raise unsupported_field(key)
        if key not in allowed:
            raise unsupported_field(key)
    if body.get("n") not in (None, 1):
        raise unsupported_field("n")
