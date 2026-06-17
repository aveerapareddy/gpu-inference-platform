"""Latency-aware scheduler policy. Owner: scheduler service."""

from __future__ import annotations

from uuid import UUID

from scheduler.models.decision import SchedulingCandidate, SchedulingDecision
from scheduler.policies.base import PolicyConfig, build_decisions


class LatencyAwarePolicy:
    """Prioritize requests with highest latency pressure.

    Score = queue_wait_duration_ms / queue_objective_ms + request_age_ms / age_objective_ms.
    Higher score is selected first. Tie-break: queue_position.

    Assumption: queue_wait and request_age reflect operator latency objectives.
    Limitation: objectives are static thresholds, not per-tenant SLOs.
    """

    policy_id = "latency_aware"
    policy_name = "LatencyAwarePolicy"

    def __init__(
        self,
        *,
        queue_objective_ms: float = 100.0,
        request_age_objective_ms: float = 5000.0,
    ) -> None:
        if queue_objective_ms <= 0 or request_age_objective_ms <= 0:
            raise ValueError("latency objectives must be positive")
        self._queue_objective_ms = queue_objective_ms
        self._request_age_objective_ms = request_age_objective_ms

    def config(self) -> PolicyConfig:
        return PolicyConfig(
            policy_id=self.policy_id,
            parameters={
                "queue_objective_ms": self._queue_objective_ms,
                "request_age_objective_ms": self._request_age_objective_ms,
            },
        )

    def _score(self, candidate: SchedulingCandidate) -> float:
        queue_pressure = candidate.queue_wait_duration_ms / self._queue_objective_ms
        age_pressure = candidate.request_age_ms / self._request_age_objective_ms
        return queue_pressure + age_pressure

    def evaluate(
        self,
        candidates: list[SchedulingCandidate],
        *,
        max_candidate_requests: int,
    ) -> tuple[list[SchedulingDecision], list[UUID], list[UUID]]:
        ordered = sorted(
            candidates,
            key=lambda c: (-self._score(c), c.queue_position, c.enqueued_at),
        )
        return build_decisions(
            ordered,
            max_candidate_requests=max_candidate_requests,
            selected_reason="latency_aware_selected",
            skipped_reason="max_candidates_reached",
        )
