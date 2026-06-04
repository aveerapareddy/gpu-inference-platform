"""Scheduler application lifecycle."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from common_schemas.states import SchedulerState as ProcessSchedulerState
from gpu_inference_observability import StructuredLogger
from gpu_inference_observability.runtime.recorder import RuntimeEventRecorder
from gpu_inference_observability.registry.recorder import RuntimeMetricsRecorder
from gpu_inference_observability.otel.manager import TraceManager

from scheduler.config import Settings, get_settings
from scheduler.batch.admission import BatchAdmissionConfig
from scheduler.batch.engine import ContinuousBatchEngine
from scheduler.batch.service import BatchService
from scheduler.loop.cycle import SchedulingCycleRunner
from scheduler.loop.runner import SchedulerLoop
from scheduler.models.decision import SchedulingResult
from scheduler.models.state import SchedulerSnapshot, SchedulerState
from scheduler.observability.batch_events import BatchEventEmitter
from scheduler.observability.events import SchedulerEventEmitter
from scheduler.queue.reader import QueueReader
from scheduler.dispatch.submitter import BatchDispatchService
from scheduler.integrations.adapter import AdapterClient
from scheduler.integrations.adapter import AdapterClient
from scheduler.integrations.embedded_adapter import EmbeddedAdapterClient
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
    batch: BatchService
    dispatch: BatchDispatchService | None
    _running: bool = False

    async def startup(self) -> None:
        if self._running:
            return
        self.logger.info(
            "scheduler starting",
            max_candidate_requests=self.settings.max_candidate_requests,
            scheduler_tick_interval_ms=self.settings.tick_interval_ms,
            queue_scan_limit=self.settings.queue_scan_limit,
            max_batch_size=self.settings.max_batch_size,
            max_active_requests=self.settings.max_active_requests,
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
        result = await self.loop.run_once()
        if self.dispatch is not None and self.settings.dispatch_enabled:
            dispatch_results = await self.dispatch.submit_pending_batches()
            result = SchedulingResult(
                cycle_id=result.cycle_id,
                cycle_start_time=result.cycle_start_time,
                cycle_end_time=result.cycle_end_time,
                decisions=result.decisions,
                selected_request_ids=result.selected_request_ids,
                skipped_request_ids=result.skipped_request_ids,
                placement_decisions=result.placement_decisions,
                rejection_decisions=result.rejection_decisions,
                dispatch_results=tuple(dispatch_results),
                failure=result.failure,
            )
        return result

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
    *,
    adapter_client: AdapterClient | None = None,
    trace_recorder: RuntimeEventRecorder | None = None,
    metrics_recorder: RuntimeMetricsRecorder | None = None,
    trace_manager: TraceManager | None = None,
) -> SchedulerApplication:
    settings = settings or get_settings()
    logger = StructuredLogger(settings.service_name)
    events = SchedulerEventEmitter(logger, settings.service_name, trace_recorder=trace_recorder)
    batch_events = BatchEventEmitter(logger, settings.service_name, trace_recorder=trace_recorder)
    batch_config = BatchAdmissionConfig(
        max_batch_size=settings.max_batch_size,
        max_active_requests=settings.max_active_requests,
        batch_admission_window_ms=settings.batch_admission_window_ms,
    )
    batch_engine = ContinuousBatchEngine(
        batch_config,
        batch_events,
        metrics_recorder=metrics_recorder,
        trace_manager=trace_manager,
    )
    batch = BatchService(batch_engine)
    state = SchedulerState()
    selector = FifoSelector()
    cycle_runner = SchedulingCycleRunner(
        queue_reader=queue_reader,
        selector=selector,
        events=events,
        settings=settings,
        state=state,
        batch=batch,
        metrics_recorder=metrics_recorder,
    )
    loop = SchedulerLoop(
        cycle_runner=cycle_runner,
        state=state,
        tick_interval_ms=settings.tick_interval_ms,
    )
    dispatch: BatchDispatchService | None = None
    if adapter_client is not None:
        dispatch = BatchDispatchService(
            batch,
            adapter_client,
            backend_id=settings.default_backend_id,
        )
    return SchedulerApplication(
        settings=settings,
        logger=logger,
        queue_reader=queue_reader,
        events=events,
        state=state,
        cycle_runner=cycle_runner,
        loop=loop,
        batch=batch,
        dispatch=dispatch,
    )
