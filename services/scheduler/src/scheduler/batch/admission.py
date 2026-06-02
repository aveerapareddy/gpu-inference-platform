"""Batch admission rules. Owner: batching engine."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum

from scheduler.batch.models import Batch, BatchState


class AdmissionDecision(StrEnum):
    ACCEPT = "accept"
    REJECT = "reject"


@dataclass(frozen=True, slots=True)
class BatchAdmissionConfig:
    max_batch_size: int
    max_active_requests: int
    batch_admission_window_ms: int

    def validate(self) -> None:
        if self.max_batch_size < 1:
            raise ValueError("max_batch_size must be >= 1")
        if self.max_active_requests < 1:
            raise ValueError("max_active_requests must be >= 1")
        if self.batch_admission_window_ms < 1:
            raise ValueError("batch_admission_window_ms must be >= 1")


@dataclass(frozen=True, slots=True)
class BatchAdmissionResult:
    decision: AdmissionDecision
    reason: str


def evaluate_batch_admission(
    *,
    batch: Batch | None,
    global_active_count: int,
    config: BatchAdmissionConfig,
    now: datetime | None = None,
) -> BatchAdmissionResult:
    """Evaluate whether a request may enter a batch."""
    now = now or datetime.now(timezone.utc)

    if global_active_count >= config.max_active_requests:
        return BatchAdmissionResult(
            decision=AdmissionDecision.REJECT,
            reason="max_active_requests_reached",
        )

    if batch is None:
        return BatchAdmissionResult(decision=AdmissionDecision.ACCEPT, reason="new_batch")

    if batch.state in {BatchState.COMPLETED, BatchState.FAILED, BatchState.CANCELLED}:
        return BatchAdmissionResult(decision=AdmissionDecision.REJECT, reason="batch_terminal")

    active_count = batch.active_member_count
    if active_count >= config.max_batch_size:
        if batch.state == BatchState.ACTIVE:
            return BatchAdmissionResult(
                decision=AdmissionDecision.REJECT,
                reason="batch_full_no_slots",
            )
        return BatchAdmissionResult(decision=AdmissionDecision.REJECT, reason="batch_full")

    if batch.state == BatchState.FILLING:
        window_end = batch.context.admission_window_end
        if now > window_end:
            return BatchAdmissionResult(
                decision=AdmissionDecision.REJECT,
                reason="admission_window_closed",
            )

    return BatchAdmissionResult(decision=AdmissionDecision.ACCEPT, reason="batch_has_capacity")
