"""Baseline benchmark suite and report generation. Owner: benchmarks.runner."""

from __future__ import annotations

import asyncio
from pathlib import Path

from gpu_inference_observability.gpu.collector import GPUMetricsCollector

from benchmarks.runner.context import StackRuntimeContext
from benchmarks.runner.embedded import run_embedded_scenario
from benchmarks.runner.models import BenchmarkRun
from benchmarks.runner.report import generate_baseline_report
from benchmarks.runner.scenarios import load_scenario
from benchmarks.runner.store import persist_run

BASELINE_SINGLE_SCENARIOS: tuple[str, ...] = (
    "baseline_single_short",
    "baseline_single_medium",
    "baseline_single_long",
    "baseline_single_streaming",
)

BASELINE_CONCURRENCY_SCENARIOS: tuple[str, ...] = (
    "baseline_concurrency_2",
    "baseline_concurrency_4",
    "baseline_concurrency_8",
)

ALL_BASELINE_SCENARIOS: tuple[str, ...] = BASELINE_SINGLE_SCENARIOS + BASELINE_CONCURRENCY_SCENARIOS


def _gpu_collector_factory(stack) -> GPUMetricsCollector:
    return GPUMetricsCollector(
        metrics_recorder=stack.metrics_recorder,
        context_provider=StackRuntimeContext(stack),
    )


async def run_baseline_suite(
    stack_factory,
    *,
    results_dir: Path | None = None,
    persist: bool = True,
    scenarios: tuple[str, ...] = ALL_BASELINE_SCENARIOS,
) -> list[BenchmarkRun]:
    runs: list[BenchmarkRun] = []
    for scenario_id in scenarios:
        scenario = load_scenario(scenario_id)
        run = await run_embedded_scenario(
            stack_factory,
            scenario,
            results_dir=results_dir,
            persist=persist,
            gpu_collector_factory=_gpu_collector_factory,
        )
        runs.append(run)
    return runs


async def run_baseline_and_report(
    stack_factory,
    *,
    results_dir: Path | None = None,
    report_path: Path | None = None,
    scenarios: tuple[str, ...] = ALL_BASELINE_SCENARIOS,
) -> tuple[list[BenchmarkRun], Path]:
    runs = await run_baseline_suite(stack_factory, results_dir=results_dir, persist=True, scenarios=scenarios)
    path = generate_baseline_report(runs, report_path=report_path)
    return runs, path


def persist_baseline_manifest(runs: list[BenchmarkRun], *, results_dir: Path) -> Path:
    manifest_path = results_dir / "baseline-manifest.json"
    payload = {
        "run_ids": [str(run.run_id) for run in runs],
        "scenario_ids": [run.scenario.scenario_id for run in runs],
    }
    manifest_path.write_text(__import__("json").dumps(payload, indent=2))
    return manifest_path
