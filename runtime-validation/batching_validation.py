#!/usr/bin/env python3
"""Session 24 batching comparison validation. Run: python runtime-validation/batching_validation.py"""

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
from gpu_inference_observability.streaming.events import StreamEventEmitter

from benchmarks.runner.batching_comparison import BATCHING_COMPARISON_SCENARIOS
from benchmarks.runner.batching_modes import BatchingMode, all_batching_mode_ids
from benchmarks.runner.batching_suite import run_batching_comparison_and_report
from benchmarks.runner.store import load_run
from harness import InjectableMockBackend, ValidationStack


def _stack_for_mode(mode: BatchingMode, concurrency: int) -> ValidationStack:
    stack = ValidationStack(
        backend=InjectableMockBackend(FailureInjector()),
        cp_settings=CPSettings(max_queue_size=max(concurrency * 2, 16), queue_timeout_ms=60_000),
        sched_settings=mode.to_sched_settings(concurrency=concurrency),
        dispatch_min_members=mode.effective_min_dispatch_members(concurrency),
    )
    stack.stack.stream_events = StreamEventEmitter(
        StructuredLogger("streaming"),
        trace_recorder=stack.trace_recorder,
    )
    return stack


async def verify_batching_suite(tmp_dir: Path) -> None:
    report_path = ROOT / "benchmarks/reports/continuous-batching-analysis.md"
    chart_dir = ROOT / "benchmarks/results/batching-comparison"
    runs, written_report, charts = await run_batching_comparison_and_report(
        _stack_for_mode,
        results_dir=tmp_dir,
        report_path=report_path,
        chart_dir=chart_dir,
    )

    assert written_report.is_file()
    assert len(charts) == 3
    for chart in charts:
        assert chart.is_file()
        assert chart.read_text().startswith("<svg")

    expected_runs = len(BATCHING_COMPARISON_SCENARIOS) * len(all_batching_mode_ids())
    assert len(runs) == expected_runs

    for run in runs:
        assert run.environment is not None
        assert run.batching_mode in all_batching_mode_ids()
        assert run.batching_config
        assert run.summary is not None
        assert run.summary.successful_requests == run.scenario.request_count
        assert run.summary.latency_ms_p50 is not None
        assert run.summary.latency_ms_p95 is not None
        assert run.summary.latency_ms_p99 is not None
        loaded = load_run(run.run_id, results_dir=tmp_dir)
        assert loaded.batching_mode == run.batching_mode
        assert loaded.run_id == run.run_id

    modes = {run.batching_mode for run in runs}
    assert modes == set(all_batching_mode_ids())

    static_c4 = next(
        r for r in runs if r.batching_mode == "static_batching" and r.scenario.concurrency == 4
    )
    members = [r.batch_member_count_at_dispatch for r in static_c4.results if r.batch_member_count_at_dispatch]
    assert members and all(m == 4 for m in members)


async def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        await verify_batching_suite(Path(tmp))
    print("batching_validation: all scenarios passed")


if __name__ == "__main__":
    asyncio.run(main())
