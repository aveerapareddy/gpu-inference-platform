"""Benchmark runner package."""

from benchmarks.runner.baseline import ALL_BASELINE_SCENARIOS, run_baseline_and_report, run_baseline_suite
from benchmarks.runner.embedded import run_embedded_scenario
from benchmarks.runner.models import (
    BenchmarkEnvironment,
    BenchmarkResult,
    BenchmarkRun,
    BenchmarkScenario,
    BenchmarkSummary,
    HardwareMetadata,
    ModelMetadata,
)
from benchmarks.runner.profiles import PROFILES, WorkloadProfile, estimated_input_tokens_for_profile, get_profile
from benchmarks.runner.report import generate_baseline_report
from benchmarks.runner.scenarios import load_scenario, list_scenario_ids
from benchmarks.runner.store import load_run, persist_run

__all__ = [
    "ALL_BASELINE_SCENARIOS",
    "BenchmarkEnvironment",
    "BenchmarkResult",
    "BenchmarkRun",
    "BenchmarkScenario",
    "BenchmarkSummary",
    "HardwareMetadata",
    "ModelMetadata",
    "PROFILES",
    "WorkloadProfile",
    "estimated_input_tokens_for_profile",
    "generate_baseline_report",
    "get_profile",
    "list_scenario_ids",
    "load_run",
    "load_scenario",
    "persist_run",
    "run_baseline_and_report",
    "run_baseline_suite",
    "run_embedded_scenario",
]
