"""Submit scheduler batches to inference adapter with routing."""

from __future__ import annotations

from uuid import uuid4

from scheduler.integrations.routing import RoutingEnginePort
from scheduler.batch.models import BatchState
from scheduler.batch.service import BatchService
from scheduler.dispatch.models import BatchDispatchResult
from scheduler.dispatch.builder import build_dispatch_batch
from scheduler.integrations.adapter import AdapterClient


class BatchDispatchService:
    """Submits ACTIVE batches once. Uses RoutingEngine when configured."""

    def __init__(
        self,
        batch_service: BatchService,
        adapter: AdapterClient,
        *,
        backend_id: str,
        routing_engine: RoutingEnginePort | None = None,
        min_dispatch_members: int | None = None,
    ) -> None:
        self._batch = batch_service
        self._adapter = adapter
        self._default_backend_id = backend_id
        self._routing = routing_engine
        self._min_dispatch_members = min_dispatch_members
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
            if (
                self._min_dispatch_members is not None
                and batch.active_member_count < self._min_dispatch_members
            ):
                continue

            assignments = self._batch.get_batch_assignments(batch.batch_id)
            result = await self._submit_batch(batch, assignments, batch_key)
            if result is not None:
                results.append(result)
        return results

    async def _submit_batch(self, batch, assignments, batch_key: str) -> BatchDispatchResult | None:
        request_id = assignments[0].request_id if assignments else uuid4()
        model_id = batch.context.model
        excluded: frozenset[str] = frozenset()
        last_error = "routing_failed"

        while True:
            backend_id = self._default_backend_id
            if self._routing is not None:
                route = self._routing.route(
                    request_id=request_id,
                    model_id=model_id,
                    excluded_backend_ids=excluded,
                )
                if not route.success or route.decision is None:
                    return BatchDispatchResult(
                        batch_id=batch_key,
                        backend_id=self._default_backend_id,
                        accepted=False,
                        reason=route.error or last_error,
                    )
                backend_id = route.decision.backend_id

            dispatch = build_dispatch_batch(batch, assignments, backend_id=backend_id)
            if dispatch is None:
                return None

            try:
                adapter_result = await self._adapter.submit_batch(
                    dispatch,
                    backend_id=backend_id,
                )
            except Exception as exc:
                if self._routing is not None:
                    excluded = excluded | {backend_id}
                    last_error = str(exc)
                    retry = self._routing.route(
                        request_id=request_id,
                        model_id=model_id,
                        excluded_backend_ids=excluded,
                    )
                    if retry.success and retry.decision is not None:
                        continue
                return BatchDispatchResult(
                    batch_id=batch_key,
                    backend_id=backend_id,
                    accepted=False,
                    reason=str(exc),
                )

            if adapter_result.accepted:
                self._submitted_batch_ids.add(batch_key)
                return BatchDispatchResult(
                    batch_id=batch_key,
                    backend_id=adapter_result.backend_id,
                    accepted=True,
                    reason=adapter_result.reason,
                )

            if self._routing is not None:
                excluded = excluded | {backend_id}
                last_error = adapter_result.reason
                continue

            return BatchDispatchResult(
                batch_id=batch_key,
                backend_id=adapter_result.backend_id,
                accepted=False,
                reason=adapter_result.reason,
            )

    async def submit_batch_by_id(self, batch_id) -> BatchDispatchResult | None:
        batch = self._batch.get_batch(batch_id)
        if batch is None:
            return None
        assignments = self._batch.get_batch_assignments(batch_id)
        return await self._submit_batch(batch, assignments, str(batch.batch_id))
