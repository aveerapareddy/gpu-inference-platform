"""Adapter client interface. Scheduler depends on this, not backend implementations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from common_schemas.batch import Batch as DispatchBatch


@dataclass(frozen=True, slots=True)
class AdapterBatchSubmitResult:
    batch_id: UUID
    backend_id: str
    accepted: bool
    reason: str


class AdapterClient(Protocol):
    async def submit_batch(
        self,
        batch: DispatchBatch,
        *,
        backend_id: str | None = None,
    ) -> AdapterBatchSubmitResult:
        """Submit dispatch batch to inference adapter."""
