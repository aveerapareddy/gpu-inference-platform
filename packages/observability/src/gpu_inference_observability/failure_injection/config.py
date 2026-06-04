"""Failure injection configuration. Deterministic, no random failures."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID


class ComponentName(StrEnum):
    GATEWAY = "gateway"
    CONTROL_PLANE = "control_plane"
    QUEUE = "queue"
    SCHEDULER = "scheduler"
    BATCH = "batch"
    ADAPTER = "adapter"
    BACKEND = "backend"


class FailurePoint(StrEnum):
    DISABLED = "disabled"

    QUEUE_FULL = "queue_full"
    QUEUE_TIMEOUT = "queue_timeout"
    QUEUE_CORRUPTION = "queue_corruption"
    QUEUE_INVALID_REMOVAL = "queue_invalid_removal"

    SCHEDULER_CRASH = "scheduler_crash"
    SCHEDULER_TIMEOUT = "scheduler_timeout"
    SCHEDULER_INVALID_DECISION = "scheduler_invalid_decision"
    SCHEDULER_INVALID_BATCH_ASSIGNMENT = "scheduler_invalid_batch_assignment"

    BATCH_CREATION_FAILURE = "batch_creation_failure"
    BATCH_ADMISSION_FAILURE = "batch_admission_failure"
    BATCH_CANCELLATION = "batch_cancellation"
    BATCH_CORRUPTION = "batch_corruption"

    BACKEND_UNAVAILABLE = "backend_unavailable"
    BACKEND_TIMEOUT = "backend_timeout"
    BACKEND_REJECTION = "backend_rejection"
    BACKEND_INTERNAL_ERROR = "backend_internal_error"


@dataclass(slots=True)
class FailureInjectionConfig:
    """Single active failure point. Reproducible when enabled."""

    enabled: bool = False
    point: FailurePoint = FailurePoint.DISABLED
    component: ComponentName | None = None
    target_request_id: UUID | None = None
    message: str = "injected failure"
    extra: dict[str, str] = field(default_factory=dict)

    def is_active(self, point: FailurePoint, *, request_id: UUID | None = None) -> bool:
        if not self.enabled or self.point != point:
            return False
        if self.target_request_id is not None and request_id is not None:
            return self.target_request_id == request_id
        return True
