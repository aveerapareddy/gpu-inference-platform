"""Shortest-job-first scheduler policy. Owner: scheduler service."""

from __future__ import annotations

from uuid import UUID

from scheduler.models.decision import SchedulingCandidate, SchedulingDecision
from scheduler.policies.base import PolicyConfig, build_decisions


class ShortestJobFirstPolicy:
    """Select candidates with smallest estimated job size first.

    Estimation: estimated_input_tokens + max_tokens from queue metadata.
    Assumption: output length is bounded by max_tokens; input size is static per request.
    Limitation: does not measure actual runtime; mock backend ignores job size.
    """

    policy_id = "shortest_job_first"
    policy_name = "ShortestJobFirstPolicy"

    def config(self) -> PolicyConfig:
        return PolicyConfig(
            policy_id=self.policy_id,
            parameters={"estimation": "estimated_input_tokens + max_tokens"},
        )

    def evaluate(
        self,
        candidates: list[SchedulingCandidate],
        *,
        max_candidate_requests: int,
    ) -> tuple[list[SchedulingDecision], list[UUID], list[UUID]]:
        ordered = sorted(
            candidates,
            key=lambda c: (c.estimated_job_tokens, c.queue_position, c.enqueued_at),
        )
        return build_decisions(
            ordered,
            max_candidate_requests=max_candidate_requests,
            selected_reason="sjf_selected",
            skipped_reason="max_candidates_reached",
        )
