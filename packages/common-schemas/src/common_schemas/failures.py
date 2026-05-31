"""Terminal failure types."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from common_schemas.states import Component, FailureReason, RequestState

FailureStatus = Literal["failed", "rejected", "timed_out", "cancelled"]


class FailureRecord(BaseModel):
    """Written by the component that detects failure."""

    model_config = ConfigDict(extra="forbid", strict=True)

    request_id: UUID
    status: FailureStatus
    failure_reason: FailureReason
    failed_at: datetime
    component: Component
    message: str | None = None
    last_state: RequestState | None = None
