"""Continuous batching engine. No inference execution."""

from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from common_schemas.batch import BatchAssignment
from common_schemas.queue import QueueItem

from gpu_inference_observability.registry.recorder import RuntimeMetricsRecorder

from scheduler.batch.active_set import ActiveRequestSet
from scheduler.batch.admission import (
    AdmissionDecision,
    BatchAdmissionConfig,
    evaluate_batch_admission,
)
from scheduler.batch.models import (
    BATCH_TERMINAL_STATES,
    Batch,
    BatchContext,
    BatchMember,
    BatchResult,
    BatchState,
    MemberStatus,
)
from scheduler.batch.transitions import transition
from scheduler.models.batch_decision import BatchPlacementDecision, BatchRejectionDecision
from scheduler.observability.batch_events import BatchEventEmitter, BatchEventType


class ContinuousBatchEngine:
    """Accepts scheduler-selected requests into managed batches."""

    def __init__(
        self,
        config: BatchAdmissionConfig,
        events: BatchEventEmitter,
        *,
        metrics_recorder: RuntimeMetricsRecorder | None = None,
    ) -> None:
        config.validate()
        self._config = config
        self._events = events
        self._metrics = metrics_recorder
        self._batches: dict[UUID, Batch] = {}
        self._sets: dict[UUID, ActiveRequestSet] = {}
        self._request_to_batch: dict[UUID, UUID] = {}
        self._active_batch_by_model: dict[str, UUID] = {}
        self._assignments: dict[UUID, BatchAssignment] = {}
        self._lock = threading.RLock()

    @property
    def config(self) -> BatchAdmissionConfig:
        return self._config

    def place_selected(self, item: QueueItem) -> BatchPlacementDecision | BatchRejectionDecision:
        with self._lock:
            return self._place_selected_locked(item)

    def retire_request(
        self,
        request_id: UUID,
        *,
        status: MemberStatus,
        reason: str,
    ) -> BatchResult:
        with self._lock:
            return self._retire_request_locked(request_id, status=status, reason=reason)

    def complete_request(self, request_id: UUID) -> BatchResult:
        return self.retire_request(request_id, status=MemberStatus.COMPLETED, reason="request_completed")

    def fail_request(self, request_id: UUID, *, reason: str = "request_failed") -> BatchResult:
        return self.retire_request(request_id, status=MemberStatus.FAILED, reason=reason)

    def cancel_request(self, request_id: UUID) -> BatchResult:
        return self.retire_request(request_id, status=MemberStatus.CANCELLED, reason="request_cancelled")

    def get_batch(self, batch_id: UUID) -> Batch | None:
        with self._lock:
            return self._batches.get(batch_id)

    def list_batches(self) -> list[Batch]:
        with self._lock:
            return list(self._batches.values())

    def get_active_batch(self, model: str) -> Batch | None:
        with self._lock:
            batch_id = self._active_batch_by_model.get(model)
            if batch_id is None:
                return None
            batch = self._batches.get(batch_id)
            if batch is None or batch.state not in {BatchState.FILLING, BatchState.ACTIVE}:
                return None
            return batch

    def global_active_request_count(self) -> int:
        with self._lock:
            return sum(s.active_count() for s in self._sets.values())

    def get_assignment(self, request_id: UUID) -> BatchAssignment | None:
        with self._lock:
            return self._assignments.get(request_id)

    def get_batch_assignments(self, batch_id: UUID) -> list[BatchAssignment]:
        with self._lock:
            batch = self._batches.get(batch_id)
            if batch is None:
                return []
            assignments: list[BatchAssignment] = []
            for member in batch.active_members():
                assignment = self._assignments.get(member.request_id)
                if assignment is not None:
                    assignments.append(assignment)
            return assignments

    def _place_selected_locked(
        self,
        item: QueueItem,
    ) -> BatchPlacementDecision | BatchRejectionDecision:
        correlation_id = item.request_context.trace_id
        model = item.inference_request.model
        now = datetime.now(timezone.utc)

        if item.request_id in self._request_to_batch:
            return BatchRejectionDecision(
                request_id=item.request_id,
                decision_reason="request_already_batched",
                correlation_id=correlation_id,
            )

        batch = self._find_admittable_batch(model, now)
        if batch is None:
            full_batch = self._active_full_batch(model)
            if full_batch is not None:
                self._events.emit(
                    BatchEventType.BATCH_ADMISSION,
                    batch_id=full_batch.batch_id,
                    request_id=item.request_id,
                    correlation_id=correlation_id,
                    model=model,
                    decision_reason="batch_full_no_slots",
                )
                return BatchRejectionDecision(
                    request_id=item.request_id,
                    decision_reason="batch_full_no_slots",
                    correlation_id=correlation_id,
                    batch_id=full_batch.batch_id,
                )

        admission = evaluate_batch_admission(
            batch=batch,
            global_active_count=self._global_active_count_locked(),
            config=self._config,
            now=now,
        )

        if admission.decision == AdmissionDecision.REJECT:
            self._events.emit(
                BatchEventType.BATCH_ADMISSION,
                batch_id=batch.batch_id if batch else None,
                request_id=item.request_id,
                correlation_id=correlation_id,
                model=model,
                decision_reason=admission.reason,
            )
            return BatchRejectionDecision(
                request_id=item.request_id,
                decision_reason=admission.reason,
                correlation_id=correlation_id,
                batch_id=batch.batch_id if batch else None,
            )

        if batch is None:
            batch = self._create_batch(model, now)

        member = BatchMember(
            request_id=item.request_id,
            slot_index=self._next_slot_index(batch),
            model=model,
            correlation_id=correlation_id,
            added_at=now,
        )
        request_set = self._sets[batch.batch_id]
        request_set.add_request(member)
        batch.members = request_set.all_members()
        self._request_to_batch[item.request_id] = batch.batch_id

        self._events.emit(
            BatchEventType.REQUEST_ADDED_TO_BATCH,
            batch_id=batch.batch_id,
            request_id=item.request_id,
            correlation_id=correlation_id,
            model=model,
            decision_reason=admission.reason,
            extra={"slot_index": member.slot_index},
        )

        self._advance_batch_after_admission(batch, now)
        if self._metrics is not None:
            self._metrics.record_batch_admission(size=batch.active_member_count)
            self._update_active_batches_gauge()

        assignment = BatchAssignment(
            request_id=item.request_id,
            slot_index=member.slot_index,
            inference_request=item.inference_request,
        )
        self._assignments[item.request_id] = assignment
        return BatchPlacementDecision(
            request_id=item.request_id,
            batch_id=batch.batch_id,
            assignment=assignment,
            decision_reason=admission.reason,
            correlation_id=correlation_id,
        )

    def _retire_request_locked(
        self,
        request_id: UUID,
        *,
        status: MemberStatus,
        reason: str,
    ) -> BatchResult:
        batch_id = self._request_to_batch.get(request_id)
        if batch_id is None:
            return BatchResult(
                batch_id=uuid4(),
                request_id=request_id,
                success=False,
                decision_reason="request_not_in_batch",
            )

        batch = self._batches[batch_id]
        request_set = self._sets[batch_id]
        previous_state = batch.context.state
        member = request_set.set_status(request_id, status)
        if member is None:
            return BatchResult(
                batch_id=batch_id,
                request_id=request_id,
                success=False,
                decision_reason="member_not_found",
            )

        batch.members = request_set.all_members()
        self._events.emit(
            BatchEventType.REQUEST_REMOVED_FROM_BATCH,
            batch_id=batch_id,
            request_id=request_id,
            correlation_id=member.correlation_id,
            model=member.model,
            decision_reason=reason,
            extra={"member_status": status.value},
        )

        if status == MemberStatus.FAILED:
            self._fail_batch_locked(batch, reason)
            return BatchResult(
                batch_id=batch_id,
                request_id=request_id,
                success=True,
                decision_reason=reason,
                previous_state=previous_state,
                new_state=batch.context.state,
            )

        if request_set.active_count() == 0 and batch.context.state == BatchState.ACTIVE:
            self._complete_batch_locked(batch, reason="all_members_retired")

        return BatchResult(
            batch_id=batch_id,
            request_id=request_id,
            success=True,
            decision_reason=reason,
            previous_state=previous_state,
            new_state=batch.context.state,
        )

    def _find_admittable_batch(self, model: str, now: datetime) -> Batch | None:
        active_id = self._active_batch_by_model.get(model)
        if active_id is not None:
            batch = self._batches.get(active_id)
            if (
                batch is not None
                and batch.state not in BATCH_TERMINAL_STATES
                and batch.active_member_count < self._config.max_batch_size
            ):
                return batch

        for batch in self._batches.values():
            if batch.context.model != model:
                continue
            if batch.state == BatchState.FILLING:
                if batch.active_member_count < self._config.max_batch_size:
                    if now <= batch.context.admission_window_end:
                        return batch
        return None

    def _active_full_batch(self, model: str) -> Batch | None:
        active_id = self._active_batch_by_model.get(model)
        if active_id is None:
            return None
        batch = self._batches.get(active_id)
        if (
            batch is not None
            and batch.state == BatchState.ACTIVE
            and batch.active_member_count >= self._config.max_batch_size
        ):
            return batch
        return None

    def _create_batch(self, model: str, now: datetime) -> Batch:
        batch_id = uuid4()
        window_end = now + timedelta(milliseconds=self._config.batch_admission_window_ms)
        context = BatchContext(
            batch_id=batch_id,
            model=model,
            state=BatchState.CREATED,
            created_at=now,
            admission_window_end=window_end,
        )
        batch = Batch(context=context)
        self._batches[batch_id] = batch
        self._sets[batch_id] = ActiveRequestSet()

        self._events.emit(
            BatchEventType.BATCH_CREATED,
            batch_id=batch_id,
            model=model,
            decision_reason="new_batch",
        )
        if self._metrics is not None:
            self._metrics.record_batch_created()
            self._update_active_batches_gauge()
        self._events.emit(
            BatchEventType.BATCH_ADMISSION,
            batch_id=batch_id,
            model=model,
            decision_reason="batch_opened",
        )

        batch.context.state = transition(batch.context.state, BatchState.FILLING)
        self._active_batch_by_model[model] = batch_id
        return batch

    def _advance_batch_after_admission(self, batch: Batch, now: datetime) -> None:
        if batch.context.state == BatchState.FILLING:
            if batch.active_member_count >= self._config.max_batch_size:
                self._events.emit(
                    BatchEventType.BATCH_FULL,
                    batch_id=batch.batch_id,
                    model=batch.context.model,
                    decision_reason="max_batch_size_reached",
                )
                batch.context.state = transition(batch.context.state, BatchState.READY)
                self._activate_batch(batch, now)
            elif now >= batch.context.admission_window_end:
                batch.context.state = transition(batch.context.state, BatchState.READY)
                self._activate_batch(batch, now)
        elif batch.context.state == BatchState.READY:
            self._activate_batch(batch, now)

    def _activate_batch(self, batch: Batch, now: datetime) -> None:
        if batch.context.state != BatchState.READY:
            return
        batch.context.state = transition(batch.context.state, BatchState.ACTIVE)
        batch.context.activated_at = now
        self._active_batch_by_model[batch.context.model] = batch.batch_id

    def _complete_batch_locked(self, batch: Batch, *, reason: str) -> None:
        if batch.context.state in BATCH_TERMINAL_STATES:
            return
        previous = batch.context.state
        batch.context.state = transition(batch.context.state, BatchState.COMPLETED)
        batch.context.completed_at = datetime.now(timezone.utc)
        self._active_batch_by_model.pop(batch.context.model, None)
        self._events.emit(
            BatchEventType.BATCH_COMPLETED,
            batch_id=batch.batch_id,
            model=batch.context.model,
            decision_reason=reason,
            extra={"previous_state": previous.value},
        )
        if self._metrics is not None:
            lifetime = (batch.context.completed_at - batch.context.created_at).total_seconds()
            self._metrics.record_batch_completed(lifetime_seconds=lifetime)
            self._update_active_batches_gauge()

    def _fail_batch_locked(self, batch: Batch, reason: str) -> None:
        if batch.context.state in BATCH_TERMINAL_STATES:
            return
        previous = batch.context.state
        batch.context.state = transition(batch.context.state, BatchState.FAILED)
        batch.context.failure_reason = reason
        self._active_batch_by_model.pop(batch.context.model, None)
        self._events.emit(
            BatchEventType.BATCH_FAILED,
            batch_id=batch.batch_id,
            model=batch.context.model,
            decision_reason=reason,
            extra={"previous_state": previous.value},
        )
        if self._metrics is not None:
            failed_at = datetime.now(timezone.utc)
            lifetime = (failed_at - batch.context.created_at).total_seconds()
            self._metrics.record_batch_failed(lifetime_seconds=lifetime)
            self._update_active_batches_gauge()

    def _next_slot_index(self, batch: Batch) -> int:
        used = {m.slot_index for m in batch.members if m.status == MemberStatus.ACTIVE}
        index = 0
        while index in used:
            index += 1
        return index

    def _global_active_count_locked(self) -> int:
        return sum(s.active_count() for s in self._sets.values())

    def _update_active_batches_gauge(self) -> None:
        if self._metrics is None:
            return
        active = sum(
            1 for batch in self._batches.values() if batch.state not in BATCH_TERMINAL_STATES
        )
        self._metrics.set_active_batches(active)
