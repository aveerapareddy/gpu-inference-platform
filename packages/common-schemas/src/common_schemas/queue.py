"""Scheduler queue types. Owner: scheduler."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from common_schemas.inference_request import InferenceRequest, RequestContext
from common_schemas.states import PriorityClass


class QueueItem(BaseModel):
    """Entry in a bounded per-model queue."""

    model_config = ConfigDict(extra="forbid", strict=True)

    request_id: UUID
    inference_request: InferenceRequest
    request_context: RequestContext
    enqueued_at: datetime
    priority_class: PriorityClass
    queue_name: str = Field(min_length=1)
