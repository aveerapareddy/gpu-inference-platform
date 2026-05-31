"""Admission control extension points. No policies implemented."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from control_plane.registry.models import RegisteredRequest


class AdmissionOutcome(StrEnum):
    ACCEPT = "accept"
    REJECT = "reject"
    DEFER = "defer"


@dataclass(frozen=True, slots=True)
class AdmissionResult:
    outcome: AdmissionOutcome
    reason: str | None = None
    retry_after_ms: int | None = None


class AdmissionEvaluator(Protocol):
    async def evaluate(self, entry: RegisteredRequest) -> AdmissionResult:
        """Evaluate whether a request may proceed past admission."""


class QueueCapacityCheck(Protocol):
    async def check(self, entry: RegisteredRequest) -> AdmissionResult:
        """Evaluate queue depth against capacity limits."""


class TimeoutCheck(Protocol):
    async def check(self, entry: RegisteredRequest) -> AdmissionResult:
        """Evaluate queue wait or e2e timeout conditions."""


class PolicyEvaluator(Protocol):
    async def evaluate(self, entry: RegisteredRequest) -> AdmissionResult:
        """Evaluate priority, model, or tenant policy rules."""
