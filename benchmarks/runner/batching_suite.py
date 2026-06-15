"""Batching comparison suite orchestration. Owner: benchmarks.runner."""

from __future__ import annotations

from pathlib import Path

from benchmarks.runner.batching_comparison import BATCHING_COMPARISON_SCENARIOS, run_batching_comparison
from benchmarks.runner.batching_modes import BatchingMode, all_batching_mode_ids, get_batching_mode
from benchmarks.runner.batching_report import generate_batching_analysis_report
from benchmarks.runner.charts import generate_batching_charts
from benchmarks.runner.models import BenchmarkRun
from benchmarks.runner.scenarios import load_scenario


async def run_batching_comparison_suite(
    stack_factory,
    *,
    results_dir: Path | None = None,
    scenarios: tuple[str, ...] = BATCHING_COMPARISON_SCENARIOS,
    modes: tuple[str, ...] | None = None,
) -> list[BenchmarkRun]:
    mode_ids = modes or all_batching_mode_ids()
    runs: list[BenchmarkRun] = []
    for scenario_id in scenarios:
        scenario = load_scenario(scenario_id)
        for mode_id in mode_ids:
            mode = get_batching_mode(mode_id)
            stack = stack_factory(mode, scenario.concurrency)
            run = await run_batching_comparison(
                stack,
                scenario,
                mode,
                results_dir=results_dir,
                persist=results_dir is not None,
            )
            runs.append(run)
    return runs


async def run_batching_comparison_and_report(
    stack_factory,
    *,
    results_dir: Path | None = None,
    report_path: Path | None = None,
    chart_dir: Path | None = None,
    scenarios: tuple[str, ...] = BATCHING_COMPARISON_SCENARIOS,
    modes: tuple[str, ...] | None = None,
) -> tuple[list[BenchmarkRun], Path, list[Path]]:
    runs = await run_batching_comparison_suite(
        stack_factory,
        results_dir=results_dir,
        scenarios=scenarios,
        modes=modes,
    )
    report = generate_batching_analysis_report(runs, report_path=report_path)
    charts = generate_batching_charts(runs, output_dir=chart_dir)
    return runs, report, charts
