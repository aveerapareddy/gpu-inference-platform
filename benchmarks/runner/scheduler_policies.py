"""Scheduler policy definitions for benchmarks. Owner: benchmarks.runner."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from scheduler.config import Settings


@dataclass(frozen=True, slots=True)
class SchedulerPolicyMode:
    policy_id: str
    name: str
    description: str

    def to_sched_settings(self, *, concurrency: int, base: Settings | None = None) -> Settings:
        base_settings = base or Settings()
        return base_settings.model_copy(
            update={
                "scheduler_policy_id": self.policy_id,
                "max_candidate_requests": max(concurrency, 1),
            }
        )

    def to_config_dict(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "name": self.name,
            "description": self.description,
        }


FIFO_POLICY = SchedulerPolicyMode(
    policy_id="fifo",
    name="FIFOSchedulerPolicy",
    description="Oldest queued request first; baseline ordering",
)

SHORTEST_JOB_FIRST_POLICY = SchedulerPolicyMode(
    policy_id="shortest_job_first",
    name="ShortestJobFirstPolicy",
    description="Smallest estimated_job_tokens first (input estimate + max_tokens)",
)

LATENCY_AWARE_POLICY = SchedulerPolicyMode(
    policy_id="latency_aware",
    name="LatencyAwarePolicy",
    description="Highest queue_wait/age pressure relative to static objectives",
)

FAIRNESS_POLICY = SchedulerPolicyMode(
    policy_id="fairness",
    name="FairnessPolicy",
    description="Deficit fairness across priority_class weights",
)

SCHEDULER_POLICIES: dict[str, SchedulerPolicyMode] = {
    p.policy_id: p
    for p in (FIFO_POLICY, SHORTEST_JOB_FIRST_POLICY, LATENCY_AWARE_POLICY, FAIRNESS_POLICY)
}


def get_scheduler_policy(policy_id: str) -> SchedulerPolicyMode:
    policy = SCHEDULER_POLICIES.get(policy_id)
    if policy is None:
        raise KeyError(f"unknown scheduler policy: {policy_id}")
    return policy


def all_scheduler_policy_ids() -> tuple[str, ...]:
    return tuple(SCHEDULER_POLICIES.keys())
