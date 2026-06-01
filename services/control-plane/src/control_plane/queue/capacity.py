"""Queue capacity configuration and overflow decisions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class QueueCapacityDecision(StrEnum):
    ACCEPT = "accept"
    REJECT = "reject"


@dataclass(frozen=True, slots=True)
class QueueCapacityConfig:
    max_queue_size: int
    queue_timeout_ms: int

    def validate(self) -> None:
        if self.max_queue_size < 1:
            raise ValueError("max_queue_size must be >= 1")
        if self.queue_timeout_ms < 1:
            raise ValueError("queue_timeout_ms must be >= 1")


@dataclass(frozen=True, slots=True)
class QueueCapacityResult:
    decision: QueueCapacityDecision
    reason: str | None = None
    retry_after_ms: int | None = None


def evaluate_enqueue_capacity(*, current_depth: int, config: QueueCapacityConfig) -> QueueCapacityResult:
    if current_depth >= config.max_queue_size:
        return QueueCapacityResult(
            decision=QueueCapacityDecision.REJECT,
            reason="queue_full",
            retry_after_ms=250,
        )
    return QueueCapacityResult(decision=QueueCapacityDecision.ACCEPT)
