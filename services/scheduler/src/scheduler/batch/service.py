"""Batch service facade."""

from __future__ import annotations

from uuid import UUID

from common_schemas.queue import QueueItem

from scheduler.batch.engine import ContinuousBatchEngine
from scheduler.batch.inspection import BatchInspection
from scheduler.batch.models import Batch, BatchResult, BatchSnapshot, BatchStatistics, MemberStatus
from scheduler.models.batch_decision import BatchPlacementDecision, BatchRejectionDecision


class BatchService:
    def __init__(self, engine: ContinuousBatchEngine) -> None:
        self._engine = engine
        self._inspection = BatchInspection(engine)

    def place_selected(
        self,
        item: QueueItem,
    ) -> BatchPlacementDecision | BatchRejectionDecision:
        return self._engine.place_selected(item)

    def complete_request(self, request_id: UUID) -> BatchResult:
        return self._engine.complete_request(request_id)

    def fail_request(self, request_id: UUID, *, reason: str = "request_failed") -> BatchResult:
        return self._engine.fail_request(request_id, reason=reason)

    def cancel_request(self, request_id: UUID) -> BatchResult:
        return self._engine.cancel_request(request_id)

    def get_batch(self, batch_id: UUID) -> Batch | None:
        return self._inspection.get_batch(batch_id)

    def list_batches(self) -> list[Batch]:
        return self._inspection.list_batches()

    def get_active_batch(self, model: str) -> Batch | None:
        return self._inspection.get_active_batch(model)

    def get_batch_snapshot(self, batch_id: UUID) -> BatchSnapshot | None:
        return self._inspection.get_batch_snapshot(batch_id)

    def get_batch_statistics(self) -> BatchStatistics:
        return self._inspection.get_batch_statistics()

    def list_active_requests(self) -> list:
        members = []
        for batch in self._engine.list_batches():
            members.extend(batch.active_members())
        return members

    def add_request(self, item: QueueItem) -> BatchPlacementDecision | BatchRejectionDecision:
        return self.place_selected(item)

    def remove_request(self, request_id: UUID) -> BatchResult:
        return self.complete_request(request_id)

    def replace_request(
        self,
        request_id: UUID,
        item: QueueItem,
    ) -> BatchPlacementDecision | BatchRejectionDecision | BatchResult:
        retire = self.complete_request(request_id)
        if not retire.success:
            return retire
        return self.place_selected(item)
