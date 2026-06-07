"""Backend request/response models. Owner: inference adapter."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from common_schemas.batch import Batch as DispatchBatch


class RequestExecutionStatus(StrEnum):
    """Per-request status returned by a backend."""

    SUBMITTED = "submitted"
    ACKNOWLEDGED = "acknowledged"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"
    UNKNOWN = "unknown"


class BackendHealthState(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class RequestCompletionResult:
    request_id: UUID
    backend_id: str
    generated_text: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    finish_reason: str | None
    completed_at: datetime
    execution_duration_ms: float | None = None
    status: RequestExecutionStatus = RequestExecutionStatus.COMPLETED


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
    completions: tuple[RequestCompletionResult, ...] = field(default_factory=tuple)


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
