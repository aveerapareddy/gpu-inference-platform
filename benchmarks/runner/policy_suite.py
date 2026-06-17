"""Scheduler policy comparison suite. Owner: benchmarks.runner."""

from __future__ import annotations

from pathlib import Path

from benchmarks.runner.models import BenchmarkRun
from benchmarks.runner.policy_comparison import run_policy_comparison
from benchmarks.runner.policy_report import POLICY_COMPARISON_SCENARIOS, generate_policy_analysis_report
from benchmarks.runner.scheduler_policies import SchedulerPolicyMode, all_scheduler_policy_ids, get_scheduler_policy
from benchmarks.runner.scenarios import load_scenario


async def run_policy_comparison_suite(
    stack_factory,
    *,
    results_dir: Path | None = None,
    scenarios: tuple[str, ...] = POLICY_COMPARISON_SCENARIOS,
    policies: tuple[str, ...] | None = None,
) -> list[BenchmarkRun]:
    policy_ids = policies or all_scheduler_policy_ids()
    runs: list[BenchmarkRun] = []
    for scenario_id in scenarios:
        scenario = load_scenario(scenario_id)
        for policy_id in policy_ids:
            policy = get_scheduler_policy(policy_id)
            stack = stack_factory(policy, scenario.concurrency)
            run = await run_policy_comparison(
                stack,
                scenario,
                policy,
                results_dir=results_dir,
                persist=results_dir is not None,
            )
            runs.append(run)
    return runs


async def run_policy_comparison_and_report(
    stack_factory,
    *,
    results_dir: Path | None = None,
    report_path: Path | None = None,
    scenarios: tuple[str, ...] = POLICY_COMPARISON_SCENARIOS,
    policies: tuple[str, ...] | None = None,
) -> tuple[list[BenchmarkRun], Path]:
    runs = await run_policy_comparison_suite(
        stack_factory,
        results_dir=results_dir,
        scenarios=scenarios,
        policies=policies,
    )
    report = generate_policy_analysis_report(runs, report_path=report_path)
    return runs, report
