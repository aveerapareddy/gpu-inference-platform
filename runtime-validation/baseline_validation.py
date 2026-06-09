#!/usr/bin/env python3
"""Session 23 baseline validation. Run: python runtime-validation/baseline_validation.py"""

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

from benchmarks.runner.baseline import (
    ALL_BASELINE_SCENARIOS,
    BASELINE_CONCURRENCY_SCENARIOS,
    BASELINE_SINGLE_SCENARIOS,
    run_baseline_and_report,
)
from benchmarks.runner.profiles import PROFILES, estimated_input_tokens_for_profile
from benchmarks.runner.store import load_run
from harness import InjectableMockBackend, ValidationStack


def _stack() -> ValidationStack:
    stack = ValidationStack(backend=InjectableMockBackend(FailureInjector()))
    stack.stack.stream_events = StreamEventEmitter(
        StructuredLogger("streaming"),
        trace_recorder=stack.trace_recorder,
    )
    return stack


def verify_workload_definitions() -> None:
    for profile_id in ("short_prompt", "medium_prompt", "long_prompt", "streaming"):
        profile = PROFILES[profile_id]
        assert profile.target_output_tokens > 0
        assert profile.rationale
        assert estimated_input_tokens_for_profile(profile) > 0


async def verify_baseline_suite(tmp_dir: Path) -> None:
    report_path = ROOT / "benchmarks/reports/baseline-results.md"
    runs, written = await run_baseline_and_report(
        _stack,
        results_dir=tmp_dir,
        report_path=report_path,
        scenarios=ALL_BASELINE_SCENARIOS,
    )
    assert written.is_file()
    assert len(runs) == len(ALL_BASELINE_SCENARIOS)

    for run in runs:
        assert run.environment is not None
        assert run.environment.model_name == "demo"
        assert run.environment.python_version
        assert run.environment.os
        assert run.summary is not None
        assert run.summary.total_requests == run.scenario.request_count
        assert run.summary.successful_requests == run.scenario.request_count
        loaded = load_run(run.run_id, results_dir=tmp_dir)
        assert loaded.environment is not None
        assert loaded.run_id == run.run_id

    single = [r for r in runs if r.scenario.scenario_id in BASELINE_SINGLE_SCENARIOS]
    assert len(single) == len(BASELINE_SINGLE_SCENARIOS)
    for run in single:
        result = run.results[0]
        assert result.latency_ms is not None
        assert result.estimated_input_tokens > 0

    streaming = next(r for r in runs if r.scenario.scenario_id == "baseline_single_streaming")
    assert streaming.results[0].ttft_ms is not None
    assert streaming.results[0].stream is True

    for scenario_id in BASELINE_CONCURRENCY_SCENARIOS:
        run = next(r for r in runs if r.scenario.scenario_id == scenario_id)
        summary = run.summary
        assert summary is not None
        assert summary.latency_ms_p50 is not None
        assert summary.latency_ms_p95 is not None
        assert summary.latency_ms_p99 is not None
        assert summary.throughput_rps is not None


async def main() -> None:
    verify_workload_definitions()
    with tempfile.TemporaryDirectory() as tmp:
        await verify_baseline_suite(Path(tmp))
    print("baseline_validation: all scenarios passed")


if __name__ == "__main__":
    asyncio.run(main())
