"""Scheduler tick loop."""

from __future__ import annotations

import asyncio

from scheduler.loop.cycle import SchedulingCycleRunner
from scheduler.models.decision import SchedulingResult
from scheduler.models.state import SchedulerState


class SchedulerLoop:
    """Periodic queue inspection and decision generation."""

    def __init__(
        self,
        cycle_runner: SchedulingCycleRunner,
        state: SchedulerState,
        *,
        tick_interval_ms: int,
    ) -> None:
        self._runner = cycle_runner
        self._state = state
        self._tick_interval_ms = tick_interval_ms
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    async def start(self) -> None:
        if self._task is not None:
            return
        self._stop.clear()
        self._state.loop_running = True
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        self._state.loop_running = False

    async def run_once(self) -> SchedulingResult:
        """Execute a single cycle outside the loop (for tests and manual ticks)."""
        return await asyncio.to_thread(self._runner.run_cycle)

    async def _run(self) -> None:
        interval = self._tick_interval_ms / 1000.0
        while not self._stop.is_set():
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=interval)
                break
            except asyncio.TimeoutError:
                pass
            if self._stop.is_set():
                break
            await asyncio.to_thread(self._runner.run_cycle)
