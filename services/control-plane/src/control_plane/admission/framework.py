"""Admission framework wiring. Default: accept (no policies)."""

from __future__ import annotations

from control_plane.admission.interfaces import (
    AdmissionEvaluator,
    AdmissionOutcome,
    AdmissionResult,
    PolicyEvaluator,
    QueueCapacityCheck,
    TimeoutCheck,
)
from control_plane.registry.models import RegisteredRequest


class _DefaultAccept:
    async def evaluate(self, entry: RegisteredRequest) -> AdmissionResult:
        return AdmissionResult(outcome=AdmissionOutcome.ACCEPT)


class AdmissionFramework:
    def __init__(
        self,
        evaluators: list[AdmissionEvaluator] | None = None,
        queue_checks: list[QueueCapacityCheck] | None = None,
        timeout_checks: list[TimeoutCheck] | None = None,
        policy_evaluators: list[PolicyEvaluator] | None = None,
    ) -> None:
        self._evaluators = evaluators or []
        self._queue_checks = queue_checks or []
        self._timeout_checks = timeout_checks or []
        self._policy_evaluators = policy_evaluators or []

    async def evaluate(self, entry: RegisteredRequest) -> AdmissionResult:
        checks: list = [
            *self._evaluators,
            *self._queue_checks,
            *self._timeout_checks,
            *self._policy_evaluators,
        ]
        if not checks:
            return await _DefaultAccept().evaluate(entry)

        for check in checks:
            if hasattr(check, "check"):
                result = await check.check(entry)
            elif hasattr(check, "evaluate"):
                result = await check.evaluate(entry)
            else:
                continue
            if result.outcome != AdmissionOutcome.ACCEPT:
                return result
        return AdmissionResult(outcome=AdmissionOutcome.ACCEPT)
