"""Benchmark batching mode definitions. Owner: benchmarks.runner."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from scheduler.config import Settings


@dataclass(frozen=True, slots=True)
class BatchingMode:
    mode_id: str
    name: str
    max_batch_size: int
    batch_admission_window_ms: int
    min_dispatch_members: int | None
    description: str

    def to_sched_settings(self, *, concurrency: int) -> Settings:
        return Settings(
            max_candidate_requests=max(concurrency, 1),
            max_batch_size=self.max_batch_size,
            batch_admission_window_ms=self.batch_admission_window_ms,
            max_active_requests=max(concurrency * 2, 32),
            tick_interval_ms=60_000,
        )

    def to_config_dict(self) -> dict[str, Any]:
        return {
            "mode_id": self.mode_id,
            "name": self.name,
            "max_batch_size": self.max_batch_size,
            "batch_admission_window_ms": self.batch_admission_window_ms,
            "min_dispatch_members": self.min_dispatch_members,
            "description": self.description,
        }

    def effective_min_dispatch_members(self, concurrency: int) -> int | None:
        if self.min_dispatch_members is None:
            return None
        return min(self.min_dispatch_members, concurrency, self.max_batch_size)


NO_BATCHING_MODE = BatchingMode(
    mode_id="no_batching",
    name="NoBatchingMode",
    max_batch_size=1,
    batch_admission_window_ms=1,
    min_dispatch_members=1,
    description="One request per batch; immediate dispatch when batch has one member",
)

STATIC_BATCHING_MODE = BatchingMode(
    mode_id="static_batching",
    name="StaticBatchingMode",
    max_batch_size=4,
    batch_admission_window_ms=3_600_000,
    min_dispatch_members=4,
    description="Dispatch only when batch reaches max_batch_size; long admission window",
)

CONTINUOUS_BATCHING_MODE = BatchingMode(
    mode_id="continuous_batching",
    name="ContinuousBatchingMode",
    max_batch_size=4,
    batch_admission_window_ms=50,
    min_dispatch_members=1,
    description="Short admission window; dispatch partial batches; allow join to active batches",
)

BATCHING_MODES: dict[str, BatchingMode] = {
    m.mode_id: m
    for m in (NO_BATCHING_MODE, STATIC_BATCHING_MODE, CONTINUOUS_BATCHING_MODE)
}


def get_batching_mode(mode_id: str) -> BatchingMode:
    mode = BATCHING_MODES.get(mode_id)
    if mode is None:
        raise KeyError(f"unknown batching mode: {mode_id}")
    return mode


def all_batching_mode_ids() -> tuple[str, ...]:
    return tuple(BATCHING_MODES.keys())
