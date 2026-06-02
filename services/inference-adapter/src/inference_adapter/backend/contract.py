"""Inference backend contract. Backend-agnostic; scheduler must not import this."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from inference_adapter.backend.models import (
    BackendMetadata,
    BatchSubmitResult,
    CancelRequestResult,
    HealthCheckResult,
    RequestStatusResult,
    SubmitBatchPayload,
)


class InferenceBackend(Protocol):
    """Backend execution boundary. Implementations: mock, vLLM, TGI, etc."""

    @property
    def backend_id(self) -> str:
        """Stable backend identifier."""

    async def submit_batch(self, batch: SubmitBatchPayload) -> BatchSubmitResult:
        """Accept a dispatch batch. Does not require token generation."""

    async def get_request_status(self, request_id: UUID) -> RequestStatusResult:
        """Return current backend-side request status."""

    async def cancel_request(self, request_id: UUID) -> CancelRequestResult:
        """Request cancellation on the backend."""

    async def health_check(self) -> HealthCheckResult:
        """Report backend health."""

    async def backend_metadata(self) -> BackendMetadata:
        """Describe backend capabilities."""
