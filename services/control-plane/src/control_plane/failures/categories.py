"""Failure classification categories."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from common_schemas.states import Component, FailureReason


class FailureCategory(StrEnum):
    VALIDATION = "validation"
    ADMISSION = "admission"
    SCHEDULER = "scheduler"
    BACKEND = "backend"
    INTERNAL = "internal"


CATEGORY_OWNERSHIP: dict[FailureCategory, Component] = {
    FailureCategory.VALIDATION: Component.GATEWAY,
    FailureCategory.ADMISSION: Component.CONTROL_PLANE,
    FailureCategory.SCHEDULER: Component.SCHEDULER,
    FailureCategory.BACKEND: Component.ADAPTER,
    FailureCategory.INTERNAL: Component.CONTROL_PLANE,
}


@dataclass(frozen=True, slots=True)
class ClassifiedFailure:
    category: FailureCategory
    reason: FailureReason
    owner: Component
    message: str
    propagate_to_client: bool
    retryable: bool


class PlatformFailure(Exception):
    """Base classified failure."""

    def __init__(self, classified: ClassifiedFailure) -> None:
        self.classified = classified
        super().__init__(classified.message)


class ValidationFailure(PlatformFailure):
    def __init__(self, message: str, reason: FailureReason = FailureReason.VALIDATION_ERROR) -> None:
        super().__init__(
            ClassifiedFailure(
                category=FailureCategory.VALIDATION,
                reason=reason,
                owner=CATEGORY_OWNERSHIP[FailureCategory.VALIDATION],
                message=message,
                propagate_to_client=True,
                retryable=False,
            )
        )


class AdmissionFailure(PlatformFailure):
    def __init__(
        self,
        message: str,
        reason: FailureReason = FailureReason.QUEUE_FULL,
        *,
        retryable: bool = True,
    ) -> None:
        super().__init__(
            ClassifiedFailure(
                category=FailureCategory.ADMISSION,
                reason=reason,
                owner=CATEGORY_OWNERSHIP[FailureCategory.ADMISSION],
                message=message,
                propagate_to_client=True,
                retryable=retryable,
            )
        )


class SchedulerFailure(PlatformFailure):
    def __init__(
        self,
        message: str,
        reason: FailureReason = FailureReason.INTERNAL_ERROR,
    ) -> None:
        super().__init__(
            ClassifiedFailure(
                category=FailureCategory.SCHEDULER,
                reason=reason,
                owner=CATEGORY_OWNERSHIP[FailureCategory.SCHEDULER],
                message=message,
                propagate_to_client=True,
                retryable=True,
            )
        )


class BackendFailure(PlatformFailure):
    def __init__(
        self,
        message: str,
        reason: FailureReason = FailureReason.WORKER_ERROR,
    ) -> None:
        super().__init__(
            ClassifiedFailure(
                category=FailureCategory.BACKEND,
                reason=reason,
                owner=CATEGORY_OWNERSHIP[FailureCategory.BACKEND],
                message=message,
                propagate_to_client=True,
                retryable=False,
            )
        )


class InternalFailure(PlatformFailure):
    def __init__(
        self,
        message: str,
        reason: FailureReason = FailureReason.INTERNAL_ERROR,
    ) -> None:
        super().__init__(
            ClassifiedFailure(
                category=FailureCategory.INTERNAL,
                reason=reason,
                owner=CATEGORY_OWNERSHIP[FailureCategory.INTERNAL],
                message=message,
                propagate_to_client=False,
                retryable=False,
            )
        )
