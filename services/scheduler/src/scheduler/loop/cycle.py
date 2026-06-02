"""Single scheduler cycle execution."""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from uuid import uuid4

from common_schemas.states import SchedulerState as ProcessSchedulerState

from scheduler.config import Settings
from scheduler.models.decision import SchedulingFailure, SchedulingResult
from scheduler.models.state import SchedulerCycle, SchedulerState
from scheduler.observability.events import SchedulerEventEmitter, SchedulerEventType
from scheduler.queue.reader import QueueReader, items_to_candidates
from scheduler.selection.fifo import FifoSelector


class SchedulingCycleRunner:
    """Inspect queue, evaluate candidates, produce scheduling decisions."""

    def __init__(
        self,
        queue_reader: QueueReader,
        selector: FifoSelector,
        events: SchedulerEventEmitter,
        settings: Settings,
        state: SchedulerState,
    ) -> None:
        self._queue = queue_reader
        self._selector = selector
        self._events = events
        self._settings = settings
        self._state = state
        self._lock = threading.Lock()

    def run_cycle(self) -> SchedulingResult:
        with self._lock:
            return self._run_cycle_locked()

    def _run_cycle_locked(self) -> SchedulingResult:
        cycle_id = str(uuid4())
        start = datetime.now(timezone.utc)
        cycle = SchedulerCycle(cycle_id=cycle_id, cycle_start_time=start)
        self._state.current_cycle = cycle
        self._state.process_mode = ProcessSchedulerState.ACCEPTING

        self._events.emit(
            SchedulerEventType.SCHEDULER_CYCLE_STARTED,
            scheduler_cycle_id=cycle_id,
            extra={"queue_scan_limit": self._settings.queue_scan_limit},
        )

        try:
            items = self._queue.list_queue_items(limit=self._settings.queue_scan_limit)
            candidates = items_to_candidates(items)

            decisions, selected, skipped = self._selector.evaluate(
                candidates,
                max_candidate_requests=self._settings.max_candidate_requests,
            )

            cycle.selected_requests = [str(rid) for rid in selected]
            cycle.skipped_requests = [str(rid) for rid in skipped]
            cycle.decisions = decisions

            summary_reason = _cycle_summary_reason(len(selected), len(skipped), len(candidates))
            cycle.complete(decision_reason=summary_reason)

            for decision in decisions:
                if decision.selected:
                    candidate = _find_candidate(candidates, decision.request_id)
                    self._events.emit(
                        SchedulerEventType.REQUEST_SELECTED,
                        scheduler_cycle_id=cycle_id,
                        request_id=decision.request_id,
                        correlation_id=decision.correlation_id,
                        model=candidate.model if candidate else None,
                        decision_reason=decision.decision_reason,
                        extra={"queue_position": decision.queue_position},
                    )
                else:
                    candidate = _find_candidate(candidates, decision.request_id)
                    self._events.emit(
                        SchedulerEventType.REQUEST_SKIPPED,
                        scheduler_cycle_id=cycle_id,
                        request_id=decision.request_id,
                        correlation_id=decision.correlation_id,
                        model=candidate.model if candidate else None,
                        decision_reason=decision.decision_reason,
                        extra={"queue_position": decision.queue_position},
                    )

            end = cycle.cycle_end_time or datetime.now(timezone.utc)
            result = SchedulingResult(
                cycle_id=cycle_id,
                cycle_start_time=start,
                cycle_end_time=end,
                decisions=tuple(decisions),
                selected_request_ids=tuple(selected),
                skipped_request_ids=tuple(skipped),
                failure=None,
            )

            self._events.emit(
                SchedulerEventType.SCHEDULER_CYCLE_COMPLETED,
                scheduler_cycle_id=cycle_id,
                decision_reason=summary_reason,
                extra={
                    "selected_count": len(selected),
                    "skipped_count": len(skipped),
                    "candidate_count": len(candidates),
                },
            )

            self._state.last_completed_cycle = cycle
            self._state.total_cycles += 1
            return result

        except Exception as exc:
            failure = SchedulingFailure(
                reason="scheduler_cycle_error",
                message=str(exc),
                cycle_id=cycle_id,
            )
            cycle.failure = failure
            cycle.complete(decision_reason="scheduler_failure")
            self._state.process_mode = ProcessSchedulerState.UNAVAILABLE

            self._events.emit(
                SchedulerEventType.SCHEDULER_FAILURE,
                scheduler_cycle_id=cycle_id,
                decision_reason=failure.reason,
                extra={"message": failure.message},
            )

            end = cycle.cycle_end_time or datetime.now(timezone.utc)
            return SchedulingResult(
                cycle_id=cycle_id,
                cycle_start_time=start,
                cycle_end_time=end,
                decisions=(),
                selected_request_ids=(),
                skipped_request_ids=(),
                failure=failure,
            )
        finally:
            self._state.current_cycle = None
            if self._state.process_mode == ProcessSchedulerState.UNAVAILABLE:
                pass
            else:
                self._state.process_mode = ProcessSchedulerState.ACCEPTING


def _cycle_summary_reason(selected: int, skipped: int, total: int) -> str:
    if total == 0:
        return "queue_empty"
    if selected == 0:
        return "no_candidates_selected"
    if skipped == 0:
        return "all_candidates_selected"
    return "partial_selection"


def _find_candidate(candidates, request_id):
    for candidate in candidates:
        if candidate.request_id == request_id:
            return candidate
    return None
