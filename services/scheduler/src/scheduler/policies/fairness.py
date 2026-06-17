"""Fairness scheduler policy. Owner: scheduler service."""

from __future__ import annotations

import threading
from uuid import UUID

from common_schemas.states import PriorityClass

from scheduler.models.decision import SchedulingCandidate, SchedulingDecision
from scheduler.policies.base import PolicyConfig, build_decisions


_DEFAULT_WEIGHTS: dict[str, float] = {
    PriorityClass.ELEVATED.value: 3.0,
    PriorityClass.DEFAULT.value: 2.0,
    PriorityClass.BACKGROUND.value: 1.0,
}


class FairnessPolicy:
    """Deficit-based fairness across priority classes.

    Fairness ratio = selection_count[priority_class] / weight[priority_class].
    Select lowest ratio first (least served per weight unit). Tie-break: queue_wait desc.

    Limitation: fairness is per priority_class, not per client or model.
    State resets when policy instance is recreated.
    """

    policy_id = "fairness"
    policy_name = "FairnessPolicy"

    def __init__(
        self,
        *,
        elevated_weight: float = 3.0,
        default_weight: float = 2.0,
        background_weight: float = 1.0,
    ) -> None:
        if min(elevated_weight, default_weight, background_weight) <= 0:
            raise ValueError("fairness weights must be positive")
        self._weights = {
            PriorityClass.ELEVATED.value: elevated_weight,
            PriorityClass.DEFAULT.value: default_weight,
            PriorityClass.BACKGROUND.value: background_weight,
        }
        self._selection_counts: dict[str, int] = {k: 0 for k in self._weights}
        self._lock = threading.Lock()

    def config(self) -> PolicyConfig:
        return PolicyConfig(policy_id=self.policy_id, parameters=dict(self._weights))

    def _weight(self, priority_class: str) -> float:
        return self._weights.get(priority_class, self._weights[PriorityClass.DEFAULT.value])

    def _fairness_ratio(self, candidate: SchedulingCandidate) -> float:
        with self._lock:
            count = self._selection_counts.get(candidate.priority_class, 0)
        return count / self._weight(candidate.priority_class)

    def _record_selections(self, selected: list[SchedulingCandidate]) -> None:
        with self._lock:
            for candidate in selected:
                key = candidate.priority_class
                self._selection_counts[key] = self._selection_counts.get(key, 0) + 1

    def evaluate(
        self,
        candidates: list[SchedulingCandidate],
        *,
        max_candidate_requests: int,
    ) -> tuple[list[SchedulingDecision], list[UUID], list[UUID]]:
        ordered = sorted(
            candidates,
            key=lambda c: (
                self._fairness_ratio(c),
                -c.queue_wait_duration_ms,
                c.queue_position,
                c.enqueued_at,
            ),
        )
        selected_candidates = ordered[:max_candidate_requests]
        self._record_selections(selected_candidates)
        return build_decisions(
            ordered,
            max_candidate_requests=max_candidate_requests,
            selected_reason="fairness_selected",
            skipped_reason="max_candidates_reached",
        )
