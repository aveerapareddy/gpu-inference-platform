#!/usr/bin/env python3
"""Session 22 benchmark validation. Run: python runtime-validation/benchmark_validation.py"""

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

from gpu_inference_observability import StructuredLogger
from gpu_inference_observability.failure_injection.injector import FailureInjector
from gpu_inference_observability.streaming.events import StreamEventEmitter

from benchmarks.runner.embedded import run_embedded_scenario
from benchmarks.runner.models import BenchmarkRun
from benchmarks.runner.profiles import PROFILES, get_profile
from benchmarks.runner.scenarios import load_scenario, list_scenario_ids
from benchmarks.runner.store import load_run
from harness import InjectableMockBackend, ValidationStack


def _stack() -> ValidationStack:
    stack = ValidationStack(backend=InjectableMockBackend(FailureInjector()))
    stack.stack.stream_events = StreamEventEmitter(
        StructuredLogger("streaming"),
        trace_recorder=stack.trace_recorder,
    )
    return stack


async def verify_profiles() -> None:
    for profile_id in ("short_prompt", "medium_prompt", "long_prompt", "streaming", "mixed"):
        profile = get_profile(profile_id)
        assert profile.profile_id == profile_id
        assert profile.max_tokens > 0
    assert len(PROFILES) == 5


async def verify_scenario_definitions() -> None:
    expected = {
        "single_request",
        "low_concurrency",
        "medium_concurrency",
        "high_concurrency",
        "streaming_workload",
        "mixed_workload",
    }
    available = set(list_scenario_ids())
    assert expected.issubset(available)


async def verify_single_request_run(tmp_dir: Path) -> BenchmarkRun:
    scenario = load_scenario("single_request")
    run = await run_embedded_scenario(_stack, scenario, results_dir=tmp_dir, persist=True)
    assert run.summary is not None
    assert run.summary.total_requests == 1
    assert run.summary.successful_requests == 1
    assert run.hardware.platform
    assert run.model.model_id == "demo"
    assert run.results[0].latency_ms is not None
    loaded = load_run(run.run_id, results_dir=tmp_dir)
    assert loaded.run_id == run.run_id
    return run


async def verify_low_concurrency_run(tmp_dir: Path) -> None:
    scenario = load_scenario("low_concurrency")
    run = await run_embedded_scenario(_stack, scenario, results_dir=tmp_dir, persist=True)
    assert run.summary is not None
    assert run.summary.total_requests == 2
    assert run.summary.successful_requests == 2
    assert run.metrics_snapshot is not None


async def verify_streaming_run(tmp_dir: Path) -> None:
    scenario = load_scenario("streaming_workload")
    run = await run_embedded_scenario(_stack, scenario, results_dir=tmp_dir, persist=True)
    assert run.summary is not None
    assert run.summary.total_requests == 2
    assert any(r.stream for r in run.results)


async def verify_k6_locust_framework() -> None:
    k6_script = ROOT / "benchmarks/load-tests/k6/scenario.js"
    locust_file = ROOT / "benchmarks/load-tests/locust/locustfile.py"
    assert k6_script.is_file()
    assert locust_file.is_file()


async def main() -> None:
    await verify_profiles()
    await verify_scenario_definitions()
    await verify_k6_locust_framework()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        await verify_single_request_run(tmp_dir)
        await verify_low_concurrency_run(tmp_dir)
        await verify_streaming_run(tmp_dir)
    print("benchmark_validation: all scenarios passed")


if __name__ == "__main__":
    asyncio.run(main())
