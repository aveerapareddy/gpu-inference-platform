"""Benchmark scenario loading. Owner: benchmarks.runner."""

from __future__ import annotations

import json
from pathlib import Path

from benchmarks.runner.models import BenchmarkScenario

SCENARIOS_DIR = Path(__file__).resolve().parents[1] / "scenarios"


def load_scenario(scenario_id: str) -> BenchmarkScenario:
    path = SCENARIOS_DIR / f"{scenario_id}.json"
    if not path.is_file():
        raise FileNotFoundError(f"scenario not found: {scenario_id}")
    data = json.loads(path.read_text())
    return BenchmarkScenario.model_validate(data)


def list_scenario_ids() -> list[str]:
    return sorted(p.stem for p in SCENARIOS_DIR.glob("*.json"))
