"""Submit scheduler batches to inference adapter."""

from __future__ import annotations

from scheduler.batch.models import BatchState
from scheduler.batch.service import BatchService
from scheduler.dispatch.models import BatchDispatchResult
from scheduler.dispatch.builder import build_dispatch_batch
from scheduler.integrations.adapter import AdapterClient


class BatchDispatchService:
    """Submits ACTIVE batches once. No routing; uses configured backend_id."""

    def __init__(
        self,
        batch_service: BatchService,
        adapter: AdapterClient,
        *,
        backend_id: str,
    ) -> None:
        self._batch = batch_service
        self._adapter = adapter
        self._backend_id = backend_id
        self._submitted_batch_ids: set[str] = set()

    async def submit_pending_batches(self) -> list[BatchDispatchResult]:
        results: list[BatchDispatchResult] = []
        for batch in self._batch.list_batches():
            batch_key = str(batch.batch_id)
            if batch_key in self._submitted_batch_ids:
                continue
            if batch.state not in {BatchState.ACTIVE, BatchState.READY, BatchState.FILLING}:
                continue
            if batch.active_member_count == 0:
                continue

            assignments = self._batch.get_batch_assignments(batch.batch_id)
            dispatch = build_dispatch_batch(
                batch,
                assignments,
                backend_id=self._backend_id,
            )
            if dispatch is None:
                continue

            try:
                adapter_result = await self._adapter.submit_batch(
                    dispatch,
                    backend_id=self._backend_id,
                )
            except Exception as exc:
                results.append(
                    BatchDispatchResult(
                        batch_id=batch_key,
                        backend_id=self._backend_id,
                        accepted=False,
                        reason=str(exc),
                    )
                )
                continue
            if adapter_result.accepted:
                self._submitted_batch_ids.add(batch_key)

            results.append(
                BatchDispatchResult(
                    batch_id=batch_key,
                    backend_id=adapter_result.backend_id,
                    accepted=adapter_result.accepted,
                    reason=adapter_result.reason,
                )
            )
        return results

    async def submit_batch_by_id(self, batch_id) -> BatchDispatchResult | None:
        batch = self._batch.get_batch(batch_id)
        if batch is None:
            return None
        assignments = self._batch.get_batch_assignments(batch_id)
        dispatch = build_dispatch_batch(batch, assignments, backend_id=self._backend_id)
        if dispatch is None:
            return None
        adapter_result = await self._adapter.submit_batch(
            dispatch,
            backend_id=self._backend_id,
        )
        if adapter_result.accepted:
            self._submitted_batch_ids.add(str(batch.batch_id))
        return BatchDispatchResult(
            batch_id=str(batch.batch_id),
            backend_id=adapter_result.backend_id,
            accepted=adapter_result.accepted,
            reason=adapter_result.reason,
        )
