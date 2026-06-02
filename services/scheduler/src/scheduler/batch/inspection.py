"""Batch inspection interfaces."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from scheduler.batch.engine import ContinuousBatchEngine
from scheduler.batch.models import Batch, BatchSnapshot, BatchState, BatchStatistics, MemberStatus


class BatchInspection:
    def __init__(self, engine: ContinuousBatchEngine) -> None:
        self._engine = engine

    def get_batch(self, batch_id: UUID) -> Batch | None:
        return self._engine.get_batch(batch_id)

    def list_batches(self) -> list[Batch]:
        return self._engine.list_batches()

    def get_active_batch(self, model: str) -> Batch | None:
        return self._engine.get_active_batch(model)

    def get_batch_snapshot(self, batch_id: UUID) -> BatchSnapshot | None:
        batch = self._engine.get_batch(batch_id)
        if batch is None:
            return None
        captured = datetime.now(timezone.utc).isoformat()
        return BatchSnapshot(
            batch_id=batch.batch_id,
            model=batch.context.model,
            state=batch.context.state,
            member_count=len(batch.members),
            active_member_count=batch.active_member_count,
            members=tuple(batch.members),
            created_at=batch.context.created_at.isoformat(),
            captured_at=captured,
        )

    def get_batch_statistics(self) -> BatchStatistics:
        batches = self._engine.list_batches()
        captured = datetime.now(timezone.utc).isoformat()
        active_batches = sum(
            1 for b in batches if b.state in {BatchState.FILLING, BatchState.ACTIVE}
        )
        filling_batches = sum(1 for b in batches if b.state == BatchState.FILLING)

        total_active = 0
        total_completed = 0
        total_failed = 0
        total_cancelled = 0
        for batch in batches:
            for member in batch.members:
                if member.status == MemberStatus.ACTIVE:
                    total_active += 1
                elif member.status == MemberStatus.COMPLETED:
                    total_completed += 1
                elif member.status == MemberStatus.FAILED:
                    total_failed += 1
                elif member.status == MemberStatus.CANCELLED:
                    total_cancelled += 1

        return BatchStatistics(
            total_batches=len(batches),
            active_batches=active_batches,
            filling_batches=filling_batches,
            total_active_requests=total_active,
            total_completed_requests=total_completed,
            total_failed_requests=total_failed,
            total_cancelled_requests=total_cancelled,
            captured_at=captured,
        )
