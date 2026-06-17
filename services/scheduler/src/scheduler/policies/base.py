"""Scheduler policy contract. Owner: scheduler service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from scheduler.models.decision import SchedulingCandidate, SchedulingDecision


@dataclass(frozen=True, slots=True)
class PolicyConfig:
    """Serializable policy configuration."""

    policy_id: str
    parameters: dict[str, Any]


class SchedulerPolicy(Protocol):
    """Interchangeable request selection policy for scheduler cycles."""

    @property
    def policy_id(self) -> str: ...

    @property
    def policy_name(self) -> str: ...

    def config(self) -> PolicyConfig: ...

    def evaluate(
        self,
        candidates: list[SchedulingCandidate],
        *,
        max_candidate_requests: int,
    ) -> tuple[list[SchedulingDecision], list[UUID], list[UUID]]: ...


def build_decisions(
    ordered: list[SchedulingCandidate],
    *,
    max_candidate_requests: int,
    selected_reason: str,
    skipped_reason: str,
) -> tuple[list[SchedulingDecision], list[UUID], list[UUID]]:
    """Build selection decisions from an ordered candidate list."""
    decisions: list[SchedulingDecision] = []
    selected: list[UUID] = []
    skipped: list[UUID] = []

    for index, candidate in enumerate(ordered):
        if index < max_candidate_requests:
            decisions.append(
                SchedulingDecision(
                    request_id=candidate.request_id,
                    correlation_id=candidate.correlation_id,
                    selected=True,
                    decision_reason=selected_reason,
                    queue_position=candidate.queue_position,
                )
            )
            selected.append(candidate.request_id)
        else:
            decisions.append(
                SchedulingDecision(
                    request_id=candidate.request_id,
                    correlation_id=candidate.correlation_id,
                    selected=False,
                    decision_reason=skipped_reason,
                    queue_position=candidate.queue_position,
                )
            )
            skipped.append(candidate.request_id)

    return decisions, selected, skipped
