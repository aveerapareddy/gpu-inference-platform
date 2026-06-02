"""Embedded inference adapter client."""

from __future__ import annotations

from common_schemas.batch import Batch as DispatchBatch

from scheduler.integrations.adapter import AdapterBatchSubmitResult, AdapterClient


class EmbeddedAdapterClient:
    def __init__(self, application) -> None:
        self._app = application

    async def submit_batch(
        self,
        batch: DispatchBatch,
        *,
        backend_id: str | None = None,
    ) -> AdapterBatchSubmitResult:
        result = await self._app.submit_batch(batch, backend_id=backend_id)
        return AdapterBatchSubmitResult(
            batch_id=result.batch_id,
            backend_id=result.backend_id,
            accepted=result.accepted,
            reason=result.reason,
        )
