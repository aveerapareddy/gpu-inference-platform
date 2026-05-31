"""Batch dispatch types. Owner: scheduler."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from common_schemas.inference_request import InferenceRequest
from common_schemas.states import BatchState


class BatchAssignment(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    request_id: UUID
    slot_index: int = Field(ge=0)
    inference_request: InferenceRequest


class Batch(BaseModel):
    """Dispatch unit sent to inference adapter."""

    model_config = ConfigDict(extra="forbid", strict=True)

    batch_id: UUID
    model: str
    worker_id: str
    assignments: list[BatchAssignment] = Field(min_length=1)
    created_at: datetime
    max_batch_tokens: int | None = Field(default=None, ge=1)
    state: BatchState
