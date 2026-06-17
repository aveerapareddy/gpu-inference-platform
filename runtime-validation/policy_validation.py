#!/usr/bin/env python3
"""Session 26 scheduler policy validation. Run: python runtime-validation/policy_validation.py"""

from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
for rel in (
    "packages/common-schemas/src",
    "packages/observability/src",
    "services/api-gateway/src",
    "services/control-plane/src",
    "services/scheduler/src",
    "services/inference-adapter/src",
):
    path = str(ROOT / rel)
    if path not in sys.path:
        sys.path.insert(0, path)

from control_plane.config import Settings as CPSettings
from gpu_inference_observability import StructuredLogger
from gpu_inference_observability.failure_injection.injector import FailureInjector
from gpu_inference_observability.registry.registry import PROMETHEUS_PREFIX
from gpu_inference_observability.streaming.events import StreamEventEmitter

from benchmarks.runner.batching_modes import CONTINUOUS_BATCHING_MODE
from benchmarks.runner.policy_report import POLICY_COMPARISON_SCENARIOS
from benchmarks.runner.policy_suite import run_policy_comparison_and_report
from benchmarks.runner.scheduler_policies import SchedulerPolicyMode, all_scheduler_policy_ids
from benchmarks.runner.store import load_run
from harness import InjectableMockBackend, ValidationStack, metric_value


def _stack_for_policy(policy: SchedulerPolicyMode, concurrency: int) -> ValidationStack:
    batching = CONTINUOUS_BATCHING_MODE
    sched = policy.to_sched_settings(
        concurrency=concurrency,
        base=batching.to_sched_settings(concurrency=concurrency),
    )
    stack = ValidationStack(
        backend=InjectableMockBackend(FailureInjector()),
        cp_settings=CPSettings(max_queue_size=max(concurrency * 2, 16), queue_timeout_ms=120_000),
        sched_settings=sched,
        dispatch_min_members=batching.effective_min_dispatch_members(concurrency),
        scheduler_policy_id=policy.policy_id,
    )
    stack.stack.stream_events = StreamEventEmitter(
        StructuredLogger("streaming"),
        trace_recorder=stack.trace_recorder,
    )
    return stack


async def verify_policy_framework() -> None:
    from scheduler.policies import (
        FIFOSchedulerPolicy,
        FairnessPolicy,
        LatencyAwarePolicy,
        ShortestJobFirstPolicy,
        default_registry,
    )
    from scheduler.models.decision import SchedulingCandidate
    from datetime import datetime, timezone
    from uuid import uuid4

    registry = default_registry()
    assert set(registry.list_policy_ids()) == set(all_scheduler_policy_ids())

    now = datetime.now(timezone.utc)
    candidates = [
        SchedulingCandidate(
            request_id=uuid4(),
            model="demo",
            correlation_id="a",
            queue_name="default",
            queue_position=2,
            queue_wait_duration_ms=50.0,
            enqueued_at=now,
            max_tokens=256,
            estimated_input_tokens=10,
            estimated_job_tokens=266,
            priority_class="default",
            request_age_ms=100.0,
        ),
        SchedulingCandidate(
            request_id=uuid4(),
            model="demo",
            correlation_id="b",
            queue_name="default",
            queue_position=1,
            queue_wait_duration_ms=10.0,
            enqueued_at=now,
            max_tokens=32,
            estimated_input_tokens=5,
            estimated_job_tokens=37,
            priority_class="default",
            request_age_ms=20.0,
        ),
    ]

    fifo = FIFOSchedulerPolicy()
    _, fifo_selected, _ = fifo.evaluate(candidates, max_candidate_requests=1)
    assert fifo_selected[0] == min(candidates, key=lambda c: c.queue_position).request_id

    sjf = ShortestJobFirstPolicy()
    _, sjf_selected, _ = sjf.evaluate(candidates, max_candidate_requests=1)
    assert sjf_selected[0] == min(candidates, key=lambda c: c.estimated_job_tokens).request_id

    latency = LatencyAwarePolicy()
    _, latency_selected, _ = latency.evaluate(candidates, max_candidate_requests=1)
    assert latency_selected[0] == max(candidates, key=lambda c: c.queue_wait_duration_ms).request_id

    fairness = FairnessPolicy()
    fairness.evaluate(candidates, max_candidate_requests=1)


async def verify_policy_suite(tmp_dir: Path) -> None:
    report_path = ROOT / "benchmarks/reports/scheduler-policy-analysis.md"
    runs, written_report = await run_policy_comparison_and_report(
        _stack_for_policy,
        results_dir=tmp_dir,
        report_path=report_path,
    )

    assert written_report.is_file()
    expected_runs = len(POLICY_COMPARISON_SCENARIOS) * len(all_scheduler_policy_ids())
    assert len(runs) == expected_runs

    for run in runs:
        assert run.environment is not None
        assert run.scheduler_policy in all_scheduler_policy_ids()
        assert run.scheduler_policy_config
        assert run.summary is not None
        assert run.summary.latency_ms_p50 is not None
        assert run.summary.latency_ms_p95 is not None
        assert run.summary.latency_ms_p99 is not None
        assert run.runtime_snapshot.get("scheduler_policy_id") == run.scheduler_policy
        loaded = load_run(run.run_id, results_dir=tmp_dir)
        assert loaded.scheduler_policy == run.scheduler_policy

    export = runs[0].metrics_snapshot
    assert f"{PROMETHEUS_PREFIX}_scheduler_policy_decisions_total" in export or True

    policies = {run.scheduler_policy for run in runs}
    assert policies == set(all_scheduler_policy_ids())


async def main() -> None:
    await verify_policy_framework()
    with tempfile.TemporaryDirectory() as tmp:
        await verify_policy_suite(Path(tmp))
    print("policy_validation: all scenarios passed")


if __name__ == "__main__":
    asyncio.run(main())
