"""Scheduler contract types."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from common_schemas.inference_request import SubmitRequest
from common_schemas.states import RequestState


class SchedulingStatus(StrEnum):
    NOT_SUBMITTED = "not_submitted"
    PENDING = "pending"
    ADMITTED = "admitted"
    REJECTED = "rejected"
    QUEUED = "queued"
    SCHEDULED = "scheduled"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class SubmitAck:
    request_id: UUID
    status: SchedulingStatus
    scheduler_state: RequestState | None = None
    message: str | None = None


@dataclass(frozen=True, slots=True)
class SchedulingResult:
    request_id: UUID
    status: SchedulingStatus
    platform_state: RequestState | None = None
    message: str | None = None
