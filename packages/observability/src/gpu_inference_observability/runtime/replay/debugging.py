"""Internal debugging interfaces for replay."""

from __future__ import annotations

from typing import Any, Awaitable, Callable
from uuid import UUID

from gpu_inference_observability.runtime.replay.engine import ReplayEngine
from gpu_inference_observability.runtime.replay.models import (
    ExecutionComparison,
    ReconstructedExecution,
    ReplayRequest,
    ReplayResult,
    RequestExecutionRecord,
    RequestPayloadSnapshot,
)
from gpu_inference_observability.runtime.replay.reconstruction import reconstruct_request


class ReplayDebugService:
    """Internal replay and reconstruction API. No HTTP surface."""

    def __init__(self, engine: ReplayEngine) -> None:
        self._engine = engine

    def get_execution_record(self, request_id: UUID) -> RequestExecutionRecord | None:
        return self._engine.execution_store.get(request_id)

    def reconstruct_execution(self, request_id: UUID) -> ReconstructedExecution | None:
        return reconstruct_request(
            request_id,
            execution_store=self._engine.execution_store,
            inspector=self._engine.inspector,
        )

    async def replay_request(
        self,
        source: UUID | RequestExecutionRecord | RequestPayloadSnapshot,
        execute: Callable[[Any], Awaitable[Any]],
        *,
        replay_id: UUID | None = None,
    ) -> ReplayResult:
        from uuid import uuid4

        if isinstance(source, UUID):
            record = self.get_execution_record(source)
            if record is None:
                raise KeyError(f"no execution record for request_id={source}")
            replay_req = self._engine.replay_request_from_record(record, replay_id=replay_id)
        elif isinstance(source, RequestExecutionRecord):
            replay_req = self._engine.replay_request_from_record(source, replay_id=replay_id)
        else:
            replay_req = ReplayRequest(
                replay_id=replay_id or uuid4(),
                payload=source,
                source_request_id=None,
            )
        return await self._engine.replay(replay_req, execute)

    def compare_execution(
        self,
        original_request_id: UUID,
        replay_request_id: UUID,
    ) -> ExecutionComparison:
        original = self.get_execution_record(original_request_id)
        replay = self.get_execution_record(replay_request_id)
        if original is None:
            raise KeyError(f"no execution record for original request_id={original_request_id}")
        if replay is None:
            raise KeyError(f"no execution record for replay request_id={replay_request_id}")
        return self._engine.compare(original, replay)
