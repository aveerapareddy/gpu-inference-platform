"""Benchmark result persistence. Owner: benchmarks.runner."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

from benchmarks.runner.models import BenchmarkRun

RESULTS_DIR = Path(__file__).resolve().parents[1] / "results"


def persist_run(run: BenchmarkRun, *, results_dir: Path | None = None) -> Path:
    directory = results_dir or RESULTS_DIR
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{run.run_id}.json"
    path.write_text(run.model_dump_json(indent=2))
    return path


def load_run(run_id: UUID, *, results_dir: Path | None = None) -> BenchmarkRun:
    directory = results_dir or RESULTS_DIR
    path = directory / f"{run_id}.json"
    if not path.is_file():
        raise FileNotFoundError(str(path))
    return BenchmarkRun.model_validate(json.loads(path.read_text()))
