"""Build adapter dispatch payloads from scheduler batches."""

from __future__ import annotations

from common_schemas.batch import Batch as DispatchBatch
from common_schemas.states import BatchState as DispatchBatchState

from scheduler.batch.models import Batch, BatchState


def build_dispatch_batch(
    batch: Batch,
    assignments: list,
    *,
    backend_id: str,
) -> DispatchBatch | None:
    """Map scheduler batch + stored assignments to common_schemas dispatch unit."""
    if batch.state not in {BatchState.ACTIVE, BatchState.READY, BatchState.FILLING}:
        return None

    if not assignments:
        return None

    created_at = batch.context.activated_at or batch.context.created_at
    return DispatchBatch(
        batch_id=batch.batch_id,
        model=batch.context.model,
        worker_id=backend_id,
        assignments=assignments,
        created_at=created_at,
        state=DispatchBatchState.FORMING,
    )
