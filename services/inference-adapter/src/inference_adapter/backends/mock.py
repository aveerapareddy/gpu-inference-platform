"""Deterministic mock backend for contract validation. No tokens or GPU work."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from common_schemas.batch import Batch as DispatchBatch

from inference_adapter.backend.contract import InferenceBackend
from inference_adapter.backend.models import (
    BackendMetadata,
    BatchSubmitResult,
    CancelRequestResult,
    HealthCheckResult,
    RequestExecutionStatus,
    RequestStatusResult,
)


class MockInferenceBackend:
    """Acknowledges batches and tracks submitted request ids in memory."""

    def __init__(
        self,
        backend_id: str = "mock",
        *,
        supported_models: tuple[str, ...] = ("demo",),
        max_batch_size: int = 32,
        reject: bool = False,
    ) -> None:
        self._backend_id = backend_id
        self._supported_models = supported_models
        self._max_batch_size = max_batch_size
        self._reject = reject
        self._submitted_batches: set[UUID] = set()
        self._request_status: dict[UUID, RequestExecutionStatus] = {}

    @property
    def backend_id(self) -> str:
        return self._backend_id

    async def submit_batch(self, batch: DispatchBatch) -> BatchSubmitResult:
        now = datetime.now(timezone.utc)
        if self._reject:
            return BatchSubmitResult(
                batch_id=batch.batch_id,
                backend_id=self._backend_id,
                accepted=False,
                reason="mock_reject_enabled",
                submitted_at=now,
            )
        if batch.model not in self._supported_models:
            return BatchSubmitResult(
                batch_id=batch.batch_id,
                backend_id=self._backend_id,
                accepted=False,
                reason="unsupported_model",
                submitted_at=now,
            )
        if len(batch.assignments) > self._max_batch_size:
            return BatchSubmitResult(
                batch_id=batch.batch_id,
                backend_id=self._backend_id,
                accepted=False,
                reason="batch_too_large",
                submitted_at=now,
            )

        self._submitted_batches.add(batch.batch_id)
        for assignment in batch.assignments:
            self._request_status[assignment.request_id] = RequestExecutionStatus.ACKNOWLEDGED

        return BatchSubmitResult(
            batch_id=batch.batch_id,
            backend_id=self._backend_id,
            accepted=True,
            reason="mock_acknowledged",
            submitted_at=now,
        )

    async def get_request_status(self, request_id: UUID) -> RequestStatusResult:
        status = self._request_status.get(request_id, RequestExecutionStatus.UNKNOWN)
        return RequestStatusResult(
            request_id=request_id,
            backend_id=self._backend_id,
            status=status,
            reason=None if status != RequestExecutionStatus.UNKNOWN else "not_submitted",
        )

    async def cancel_request(self, request_id: UUID) -> CancelRequestResult:
        if request_id not in self._request_status:
            return CancelRequestResult(
                request_id=request_id,
                backend_id=self._backend_id,
                cancelled=False,
                reason="request_not_found",
            )
        self._request_status[request_id] = RequestExecutionStatus.CANCELLED
        return CancelRequestResult(
            request_id=request_id,
            backend_id=self._backend_id,
            cancelled=True,
            reason="mock_cancelled",
        )

    async def health_check(self) -> HealthCheckResult:
        return HealthCheckResult(
            backend_id=self._backend_id,
            healthy=not self._reject,
            state="healthy" if not self._reject else "unhealthy",
            message="mock backend operational" if not self._reject else "mock reject mode",
            checked_at=datetime.now(timezone.utc),
        )

    async def backend_metadata(self) -> BackendMetadata:
        return BackendMetadata(
            backend_id=self._backend_id,
            backend_type="mock",
            supported_models=self._supported_models,
            max_batch_size=self._max_batch_size,
            extra={"deterministic": True},
        )

    def was_batch_submitted(self, batch_id: UUID) -> bool:
        return batch_id in self._submitted_batches
