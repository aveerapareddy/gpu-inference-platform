#!/usr/bin/env python3
"""Session 25 concurrency scaling validation. Run: python runtime-validation/scaling_validation.py"""

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

from benchmarks.runner.bottleneck import BottleneckType, max_sustainable_concurrency
from benchmarks.runner.scaling_levels import SCALING_VALIDATION_LEVELS
from benchmarks.runner.scaling_suite import run_scaling_suite_and_report
from benchmarks.runner.store import load_run
from benchmarks.runner.batching_modes import CONTINUOUS_BATCHING_MODE
from harness import InjectableMockBackend, ValidationStack


def _stack_for_concurrency(concurrency: int) -> ValidationStack:
    mode = CONTINUOUS_BATCHING_MODE
    stack = ValidationStack(
        backend=InjectableMockBackend(FailureInjector()),
        cp_settings=CPSettings(max_queue_size=max(concurrency * 2, 16), queue_timeout_ms=120_000),
        sched_settings=mode.to_sched_settings(concurrency=concurrency),
        dispatch_min_members=mode.effective_min_dispatch_members(concurrency),
    )
    stack.stack.stream_events = StreamEventEmitter(
        StructuredLogger("streaming"),
        trace_recorder=stack.trace_recorder,
    )
    return stack


async def verify_scaling_suite(tmp_dir: Path) -> None:
    report_path = ROOT / "benchmarks/reports/concurrency-scaling-analysis.md"
    chart_dir = ROOT / "benchmarks/results/scaling-analysis"
    runs, written_report, charts, sustainable = await run_scaling_suite_and_report(
        _stack_for_concurrency,
        results_dir=tmp_dir,
        report_path=report_path,
        chart_dir=chart_dir,
        levels=SCALING_VALIDATION_LEVELS,
    )

    assert written_report.is_file()
    assert len(charts) == 6
    for chart in charts:
        assert chart.is_file()
        assert chart.read_text().startswith("<svg")

    assert len(runs) == len(SCALING_VALIDATION_LEVELS)

    for run in runs:
        assert run.environment is not None
        assert run.runner == "scaling"
        assert run.summary is not None
        assert run.bottleneck is not None
        assert run.telemetry_samples
        assert run.runtime_snapshot
        assert run.summary.latency_ms_p95 is not None
        loaded = load_run(run.run_id, results_dir=tmp_dir)
        assert loaded.run_id == run.run_id
        assert loaded.bottleneck is not None

    assert sustainable is not None
    assert sustainable >= 1

    low = next(r for r in runs if r.scenario.concurrency == 1)
    assert low.summary.successful_requests == 1
    assert low.bottleneck.primary_bottleneck in {t.value for t in BottleneckType}


async def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        await verify_scaling_suite(Path(tmp))
    print("scaling_validation: all scenarios passed")


if __name__ == "__main__":
    asyncio.run(main())
