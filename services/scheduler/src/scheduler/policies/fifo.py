"""FIFO scheduler policy. Owner: scheduler service."""

from __future__ import annotations

from scheduler.models.decision import SchedulingCandidate, SchedulingDecision
from scheduler.policies.base import PolicyConfig, SchedulerPolicy, build_decisions
from uuid import UUID


class FIFOSchedulerPolicy:
    """Select candidates in queue order (oldest first)."""

    policy_id = "fifo"
    policy_name = "FIFOSchedulerPolicy"

    def config(self) -> PolicyConfig:
        return PolicyConfig(policy_id=self.policy_id, parameters={})

    def evaluate(
        self,
        candidates: list[SchedulingCandidate],
        *,
        max_candidate_requests: int,
    ) -> tuple[list[SchedulingDecision], list[UUID], list[UUID]]:
        ordered = sorted(candidates, key=lambda c: (c.queue_position, c.enqueued_at))
        return build_decisions(
            ordered,
            max_candidate_requests=max_candidate_requests,
            selected_reason="fifo_selected",
            skipped_reason="max_candidates_reached",
        )
