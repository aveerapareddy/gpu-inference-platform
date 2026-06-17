"""Scheduler policy registration and selection. Owner: scheduler service."""

from __future__ import annotations

from typing import Callable

from scheduler.config import Settings
from scheduler.policies.base import PolicyConfig, SchedulerPolicy
from scheduler.policies.fairness import FairnessPolicy
from scheduler.policies.fifo import FIFOSchedulerPolicy
from scheduler.policies.latency_aware import LatencyAwarePolicy
from scheduler.policies.shortest_job_first import ShortestJobFirstPolicy

PolicyFactory = Callable[[Settings], SchedulerPolicy]


class SchedulerPolicyRegistry:
    """Register and resolve scheduler policies by id."""

    def __init__(self) -> None:
        self._factories: dict[str, PolicyFactory] = {}

    def register(self, policy_id: str, factory: PolicyFactory) -> None:
        if policy_id in self._factories:
            raise ValueError(f"policy already registered: {policy_id}")
        self._factories[policy_id] = factory

    def create(self, policy_id: str, settings: Settings) -> SchedulerPolicy:
        factory = self._factories.get(policy_id)
        if factory is None:
            raise KeyError(f"unknown scheduler policy: {policy_id}")
        return factory(settings)

    def list_policy_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._factories))

    def policy_configs(self, settings: Settings) -> dict[str, PolicyConfig]:
        return {pid: self.create(pid, settings).config() for pid in self.list_policy_ids()}


def _register_defaults(registry: SchedulerPolicyRegistry) -> None:
    registry.register("fifo", lambda _s: FIFOSchedulerPolicy())
    registry.register("shortest_job_first", lambda _s: ShortestJobFirstPolicy())
    registry.register(
        "latency_aware",
        lambda s: LatencyAwarePolicy(
            queue_objective_ms=s.latency_queue_objective_ms,
            request_age_objective_ms=s.latency_request_age_objective_ms,
        ),
    )
    registry.register(
        "fairness",
        lambda s: FairnessPolicy(
            elevated_weight=s.fairness_elevated_weight,
            default_weight=s.fairness_default_weight,
            background_weight=s.fairness_background_weight,
        ),
    )


_DEFAULT_REGISTRY: SchedulerPolicyRegistry | None = None


def default_registry() -> SchedulerPolicyRegistry:
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        registry = SchedulerPolicyRegistry()
        _register_defaults(registry)
        _DEFAULT_REGISTRY = registry
    return _DEFAULT_REGISTRY


def build_policy(settings: Settings) -> SchedulerPolicy:
    return default_registry().create(settings.scheduler_policy_id, settings)
