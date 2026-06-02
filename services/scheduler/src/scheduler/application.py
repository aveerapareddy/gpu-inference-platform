"""Scheduler application lifecycle."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from common_schemas.states import SchedulerState as ProcessSchedulerState
from gpu_inference_observability import StructuredLogger

from scheduler.config import Settings, get_settings
from scheduler.loop.cycle import SchedulingCycleRunner
from scheduler.loop.runner import SchedulerLoop
from scheduler.models.decision import SchedulingResult
from scheduler.models.state import SchedulerSnapshot, SchedulerState
from scheduler.observability.events import SchedulerEventEmitter
from scheduler.queue.reader import QueueReader
from scheduler.selection.fifo import FifoSelector


@dataclass
class SchedulerApplication:
    settings: Settings
    logger: StructuredLogger
    queue_reader: QueueReader
    events: SchedulerEventEmitter
    state: SchedulerState
    cycle_runner: SchedulingCycleRunner
    loop: SchedulerLoop
    _running: bool = False

    async def startup(self) -> None:
        if self._running:
            return
        self.logger.info(
            "scheduler starting",
            max_candidate_requests=self.settings.max_candidate_requests,
            scheduler_tick_interval_ms=self.settings.tick_interval_ms,
            queue_scan_limit=self.settings.queue_scan_limit,
        )
        self.state.process_mode = ProcessSchedulerState.ACCEPTING
        self._running = True
        await self.loop.start()
        self.logger.info("scheduler ready", process_mode=self.state.process_mode.value)

    async def shutdown(self) -> None:
        if not self._running:
            return
        self.logger.info("scheduler shutting down", total_cycles=self.state.total_cycles)
        await self.loop.stop()
        self.state.process_mode = ProcessSchedulerState.DRAINING
        self._running = False
        self.logger.info("scheduler stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    async def run_scheduling_cycle(self) -> SchedulingResult:
        """Run one cycle without waiting for the tick loop."""
        return await self.loop.run_once()

    def get_scheduler_snapshot(self) -> SchedulerSnapshot:
        last = self.state.last_completed_cycle
        return SchedulerSnapshot(
            process_mode=self.state.process_mode,
            loop_running=self.state.loop_running,
            total_cycles=self.state.total_cycles,
            current_cycle_id=(
                self.state.current_cycle.cycle_id if self.state.current_cycle else None
            ),
            last_cycle_id=last.cycle_id if last else None,
            last_selected_count=len(last.selected_requests) if last else 0,
            last_skipped_count=len(last.skipped_requests) if last else 0,
            last_decision_reason=last.decision_reason if last else None,
            captured_at=datetime.now(timezone.utc).isoformat(),
        )


def create_application(
    queue_reader: QueueReader,
    settings: Settings | None = None,
) -> SchedulerApplication:
    settings = settings or get_settings()
    logger = StructuredLogger(settings.service_name)
    events = SchedulerEventEmitter(logger, settings.service_name)
    state = SchedulerState()
    selector = FifoSelector()
    cycle_runner = SchedulingCycleRunner(
        queue_reader=queue_reader,
        selector=selector,
        events=events,
        settings=settings,
        state=state,
    )
    loop = SchedulerLoop(
        cycle_runner=cycle_runner,
        state=state,
        tick_interval_ms=settings.tick_interval_ms,
    )
    return SchedulerApplication(
        settings=settings,
        logger=logger,
        queue_reader=queue_reader,
        events=events,
        state=state,
        cycle_runner=cycle_runner,
        loop=loop,
    )
