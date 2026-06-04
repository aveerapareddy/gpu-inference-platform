"""Failure injector. Owner: reliability validation harness."""

from __future__ import annotations

from uuid import UUID

from gpu_inference_observability.failure_injection.config import FailureInjectionConfig, FailurePoint
from gpu_inference_observability.failure_injection.exceptions import InjectedFailure, SchedulerInjectedTimeout


class FailureInjector:
    """Deterministic failure injection controller."""

    def __init__(self, config: FailureInjectionConfig | None = None) -> None:
        self._config = config or FailureInjectionConfig()

    @property
    def config(self) -> FailureInjectionConfig:
        return self._config

    @property
    def enabled(self) -> bool:
        return self._config.enabled

    def configure(self, config: FailureInjectionConfig) -> None:
        self._config = config

    def disable(self) -> None:
        self._config = FailureInjectionConfig(enabled=False)

    def should_inject(self, point: FailurePoint, *, request_id: UUID | None = None) -> bool:
        return self._config.is_active(point, request_id=request_id)

    def maybe_raise(self, point: FailurePoint, *, request_id: UUID | None = None) -> None:
        if not self.should_inject(point, request_id=request_id):
            return
        if point == FailurePoint.SCHEDULER_TIMEOUT:
            raise SchedulerInjectedTimeout(self._config.message)
        raise InjectedFailure(point, self._config.message)
