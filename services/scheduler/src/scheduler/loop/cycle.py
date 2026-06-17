"""Single scheduler cycle execution."""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from uuid import uuid4

from common_schemas.states import SchedulerState as ProcessSchedulerState

from gpu_inference_observability.registry.recorder import RuntimeMetricsRecorder

from gpu_inference_observability.failure_injection.config import FailurePoint
from gpu_inference_observability.failure_injection.injector import FailureInjector

from scheduler.config import Settings
from scheduler.batch.service import BatchService
from scheduler.models.batch_decision import BatchPlacementDecision, BatchRejectionDecision
from scheduler.models.decision import SchedulingFailure, SchedulingResult
from scheduler.models.state import SchedulerCycle, SchedulerState
from scheduler.observability.events import SchedulerEventEmitter, SchedulerEventType
from scheduler.policies.base import SchedulerPolicy
from scheduler.queue.reader import QueueReader, items_to_candidates


class SchedulingCycleRunner:
    """Inspect queue, evaluate candidates, produce scheduling decisions."""

    def __init__(
        self,
        queue_reader: QueueReader,
        policy: SchedulerPolicy,
        events: SchedulerEventEmitter,
        settings: Settings,
        state: SchedulerState,
        batch: BatchService,
        *,
        metrics_recorder: RuntimeMetricsRecorder | None = None,
        failure_injector: FailureInjector | None = None,
    ) -> None:
        self._queue = queue_reader
        self._policy = policy
        self._events = events
        self._settings = settings
        self._state = state
        self._batch = batch
        self._metrics = metrics_recorder
        self._failure_injector = failure_injector
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
            extra={
                "queue_scan_limit": self._settings.queue_scan_limit,
                "scheduler_policy_id": self._policy.policy_id,
            },
        )

        try:
            if self._failure_injector is not None:
                self._failure_injector.maybe_raise(FailurePoint.SCHEDULER_CRASH)
                self._failure_injector.maybe_raise(FailurePoint.SCHEDULER_TIMEOUT)

            items = self._queue.list_queue_items(limit=self._settings.queue_scan_limit)
            item_by_id = {item.request_id: item for item in items}
            candidates = items_to_candidates(items)

            decisions, selected, skipped = self._policy.evaluate(
                candidates,
                max_candidate_requests=self._settings.max_candidate_requests,
            )

            candidate_by_id = {c.request_id: c for c in candidates}
            if self._metrics is not None:
                for decision in decisions:
                    candidate = candidate_by_id.get(decision.request_id)
                    if candidate is None:
                        continue
                    self._metrics.record_scheduler_policy_decision(
                        policy_id=self._policy.policy_id,
                        selected=decision.selected,
                        decision_reason=decision.decision_reason,
                        queue_wait_seconds=candidate.queue_wait_duration_ms / 1000.0,
                        request_age_seconds=candidate.request_age_ms / 1000.0,
                    )

            placements: list[BatchPlacementDecision] = []
            rejections: list[BatchRejectionDecision] = []
            for request_id in selected:
                item = item_by_id.get(request_id)
                if item is None:
                    rejections.append(
                        BatchRejectionDecision(
                            request_id=request_id,
                            decision_reason="queue_item_not_found",
                            correlation_id="",
                        )
                    )
                    continue
                outcome = self._batch.place_selected(item)
                if isinstance(outcome, BatchPlacementDecision):
                    placements.append(outcome)
                else:
                    rejections.append(outcome)

            cycle.selected_requests = [str(rid) for rid in selected]
            cycle.skipped_requests = [str(rid) for rid in skipped]
            cycle.decisions = decisions

            summary_reason = _cycle_summary_reason(
                len(placements),
                len(skipped) + len(rejections),
                len(candidates),
            )
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
                        extra={
                            "queue_position": decision.queue_position,
                            "scheduler_policy_id": self._policy.policy_id,
                            "queue_wait_duration_ms": (
                                candidate.queue_wait_duration_ms if candidate else None
                            ),
                            "request_age_ms": candidate.request_age_ms if candidate else None,
                        },
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
                        extra={
                            "queue_position": decision.queue_position,
                            "scheduler_policy_id": self._policy.policy_id,
                        },
                    )

            end = cycle.cycle_end_time or datetime.now(timezone.utc)
            result = SchedulingResult(
                cycle_id=cycle_id,
                cycle_start_time=start,
                cycle_end_time=end,
                decisions=tuple(decisions),
                selected_request_ids=tuple(selected),
                skipped_request_ids=tuple(skipped),
                placement_decisions=tuple(placements),
                rejection_decisions=tuple(rejections),
                failure=None,
            )

            self._events.emit(
                SchedulerEventType.SCHEDULER_CYCLE_COMPLETED,
                scheduler_cycle_id=cycle_id,
                decision_reason=summary_reason,
                extra={
                    "selected_count": len(selected),
                    "placed_count": len(placements),
                    "batch_rejected_count": len(rejections),
                    "skipped_count": len(skipped),
                    "candidate_count": len(candidates),
                    "scheduler_policy_id": self._policy.policy_id,
                },
            )

            self._state.last_completed_cycle = cycle
            self._state.total_cycles += 1
            if self._metrics is not None:
                duration = (end - start).total_seconds()
                self._metrics.record_scheduler_cycle(
                    selected_count=len(selected),
                    skipped_count=len(skipped),
                    duration_seconds=duration,
                    failed=False,
                )
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
                extra={"failure_message": failure.message},
            )

            end = cycle.cycle_end_time or datetime.now(timezone.utc)
            if self._metrics is not None:
                duration = (end - start).total_seconds()
                self._metrics.record_scheduler_cycle(
                    selected_count=0,
                    skipped_count=0,
                    duration_seconds=duration,
                    failed=True,
                )
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
