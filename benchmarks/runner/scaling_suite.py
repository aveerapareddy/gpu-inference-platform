"""Concurrency scaling suite orchestration. Owner: benchmarks.runner."""

from __future__ import annotations

from pathlib import Path

from benchmarks.runner.bottleneck import max_sustainable_concurrency
from benchmarks.runner.models import BenchmarkRun
from benchmarks.runner.scaling_charts import generate_scaling_charts
from benchmarks.runner.scaling_levels import SCALING_LEVELS, scaling_scenario
from benchmarks.runner.scaling_report import generate_scaling_report
from benchmarks.runner.scaling_runner import run_scaling_experiment


async def run_scaling_suite(
    stack_factory,
    *,
    results_dir: Path | None = None,
    levels: tuple[int, ...] = SCALING_LEVELS,
) -> list[BenchmarkRun]:
    runs: list[BenchmarkRun] = []
    for concurrency in levels:
        scenario = scaling_scenario(concurrency)
        stack = stack_factory(concurrency)
        run = await run_scaling_experiment(
            stack,
            scenario,
            results_dir=results_dir,
            persist=results_dir is not None,
        )
        runs.append(run)
    return runs


async def run_scaling_suite_and_report(
    stack_factory,
    *,
    results_dir: Path | None = None,
    report_path: Path | None = None,
    chart_dir: Path | None = None,
    levels: tuple[int, ...] = SCALING_LEVELS,
) -> tuple[list[BenchmarkRun], Path, list[Path], int | None]:
    runs = await run_scaling_suite(stack_factory, results_dir=results_dir, levels=levels)
    report = generate_scaling_report(runs, report_path=report_path)
    charts = generate_scaling_charts(runs, output_dir=chart_dir)
    sustainable = max_sustainable_concurrency(runs)
    return runs, report, charts, sustainable
