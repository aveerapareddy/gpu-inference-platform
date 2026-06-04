"""Injected failure exceptions."""

from __future__ import annotations

from gpu_inference_observability.failure_injection.config import FailurePoint


class InjectedFailure(Exception):
    """Raised when a configured failure point is triggered."""

    def __init__(self, point: FailurePoint, message: str | None = None) -> None:
        self.point = point
        self.message = message or f"injected failure: {point.value}"
        super().__init__(self.message)


class SchedulerInjectedTimeout(InjectedFailure):
    def __init__(self, message: str | None = None) -> None:
        super().__init__(FailurePoint.SCHEDULER_TIMEOUT, message or "scheduler cycle timeout")


class BatchInjectedFailure(InjectedFailure):
    pass
