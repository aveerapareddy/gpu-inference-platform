"""Benchmark runner package."""

from benchmarks.runner.embedded import run_embedded_scenario
from benchmarks.runner.models import (
    BenchmarkResult,
    BenchmarkRun,
    BenchmarkScenario,
    BenchmarkSummary,
    HardwareMetadata,
    ModelMetadata,
)
from benchmarks.runner.profiles import PROFILES, WorkloadProfile, get_profile
from benchmarks.runner.scenarios import load_scenario, list_scenario_ids
from benchmarks.runner.store import load_run, persist_run

__all__ = [
    "BenchmarkResult",
    "BenchmarkRun",
    "BenchmarkScenario",
    "BenchmarkSummary",
    "HardwareMetadata",
    "ModelMetadata",
    "PROFILES",
    "WorkloadProfile",
    "get_profile",
    "list_scenario_ids",
    "load_run",
    "load_scenario",
    "persist_run",
    "run_embedded_scenario",
]
