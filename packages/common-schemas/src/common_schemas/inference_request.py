"""Inference request and correlation types. Owner: API gateway."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from common_schemas.routing import ModelCapabilities, RoutingPolicyName
from common_schemas.states import MessageRole, PriorityClass


class Message(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    role: MessageRole
    content: str


class InferenceRequest(BaseModel):
    """Internal request after gateway validation."""

    model_config = ConfigDict(extra="forbid", strict=True)

    request_id: UUID
    model: str = Field(min_length=1)
    messages: list[Message] = Field(min_length=1, max_length=128)
    stream: bool
    max_tokens: int = Field(ge=1, le=32768)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)
    priority_class: PriorityClass | None = None
    api_key_id: str | None = None
    client_request_id: str | None = None


class RequestContext(BaseModel):
    """Trace and correlation context. Owner: API gateway; read-only downstream."""

    model_config = ConfigDict(extra="forbid", strict=True)

    request_id: UUID
    trace_id: str = Field(min_length=1)
    span_id: str = Field(min_length=1)
    arrival_time: datetime
    model: str
    stream: bool
    gateway_instance_id: str


class SubmitRequest(BaseModel):
    """Gateway to scheduler submit body."""

    model_config = ConfigDict(extra="forbid", strict=True)

    inference_request: InferenceRequest
    request_context: RequestContext


class ModelRecord(BaseModel):
    """Control plane model registry entry."""

    model_config = ConfigDict(extra="forbid", strict=True)

    model_id: str
    backend: str
    pool_id: str
    max_output_tokens: int = Field(ge=1)
    max_prompt_tokens: int = Field(ge=1)
    default_temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    capabilities: ModelCapabilities = Field(default_factory=ModelCapabilities)
    routing_policy: RoutingPolicyName = RoutingPolicyName.EXPLICIT
    fallback_backend: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)
