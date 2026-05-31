"""Failure propagation rules. No retry implementation."""

from __future__ import annotations

from common_schemas.failures import FailureRecord
from common_schemas.states import RequestState

from control_plane.failures.categories import (
    ClassifiedFailure,
    FailureCategory,
    PlatformFailure,
)
from control_plane.registry.models import RegisteredRequest


class FailureFramework:
    """Maps classified failures to registry state and FailureRecord shape."""

    @staticmethod
    def target_state(category: FailureCategory) -> RequestState:
        if category == FailureCategory.ADMISSION:
            return RequestState.REJECTED
        if category == FailureCategory.VALIDATION:
            return RequestState.REJECTED
        return RequestState.FAILED

    @staticmethod
    def apply_to_request(entry: RegisteredRequest, failure: ClassifiedFailure) -> None:
        entry.state = FailureFramework.target_state(failure.category)
        entry.failure_reason = failure.reason
        entry.failure_message = failure.message

    @staticmethod
    def to_failure_record(entry: RegisteredRequest, failure: ClassifiedFailure) -> FailureRecord:
        from datetime import datetime, timezone

        status_map = {
            FailureCategory.VALIDATION: "rejected",
            FailureCategory.ADMISSION: "rejected",
        }
        status = status_map.get(failure.category, "failed")
        return FailureRecord(
            request_id=entry.request_id,
            status=status,  # type: ignore[arg-type]
            failure_reason=failure.reason,
            failed_at=datetime.now(timezone.utc),
            component=failure.owner,
            message=failure.message,
            last_state=entry.state,
        )

    @staticmethod
    def from_exception(exc: PlatformFailure) -> ClassifiedFailure:
        return exc.classified
