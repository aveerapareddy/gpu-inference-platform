"""Concurrency scaling level definitions. Owner: benchmarks.runner."""

from __future__ import annotations

from benchmarks.runner.models import BenchmarkScenario

# Full scaling ladder. Validation may cap via SCALING_VALIDATION_LEVELS.
SCALING_LEVELS: tuple[int, ...] = (1, 2, 4, 8, 16, 32, 64, 128)

# Subset used in CI validation to keep runtime bounded on developer hardware.
SCALING_VALIDATION_LEVELS: tuple[int, ...] = (1, 2, 4, 8, 16, 32, 64, 128)


def scaling_scenario(concurrency: int) -> BenchmarkScenario:
    return BenchmarkScenario(
        scenario_id=f"scaling_c{concurrency}",
        name=f"scaling_c{concurrency}",
        description=f"Concurrency scaling experiment at concurrency {concurrency}",
        concurrency=concurrency,
        request_count=concurrency,
        workload_profile="streaming",
        stream=True,
    )


def scaling_scenario_ids(levels: tuple[int, ...] = SCALING_LEVELS) -> tuple[str, ...]:
    return tuple(f"scaling_c{c}" for c in levels)
