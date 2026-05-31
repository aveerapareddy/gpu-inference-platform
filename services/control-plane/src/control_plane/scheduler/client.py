"""Control plane to scheduler interface."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from common_schemas.inference_request import SubmitRequest

from control_plane.scheduler.types import SchedulingResult, SchedulingStatus, SubmitAck


class SchedulerClient(Protocol):
    async def submit_request(self, submit: SubmitRequest) -> SubmitAck:
        """Hand off a validated request to the scheduler."""

    async def get_scheduling_status(self, request_id: UUID) -> SchedulingStatus:
        """Poll scheduler-side status for a request."""

    async def receive_scheduling_result(self, request_id: UUID) -> SchedulingResult | None:
        """Fetch a terminal or progress scheduling result if available."""
