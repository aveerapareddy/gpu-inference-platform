"""Backend request/response models. Owner: inference adapter."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from common_schemas.batch import Batch as DispatchBatch


class RequestExecutionStatus(StrEnum):
    """Per-request status returned by a backend. No token generation."""

    SUBMITTED = "submitted"
    ACKNOWLEDGED = "acknowledged"
    CANCELLED = "cancelled"
    FAILED = "failed"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class BackendMetadata:
    backend_id: str
    backend_type: str
    supported_models: tuple[str, ...]
    max_batch_size: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class HealthCheckResult:
    backend_id: str
    healthy: bool
    state: str
    message: str | None = None
    checked_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class BatchSubmitResult:
    batch_id: UUID
    backend_id: str
    accepted: bool
    reason: str
    submitted_at: datetime


@dataclass(frozen=True, slots=True)
class RequestStatusResult:
    request_id: UUID
    backend_id: str
    status: RequestExecutionStatus
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class CancelRequestResult:
    request_id: UUID
    backend_id: str
    cancelled: bool
    reason: str


SubmitBatchPayload = DispatchBatch
