"""Scheduler stub. No scheduling behavior."""

from __future__ import annotations

from uuid import UUID

from common_schemas.inference_request import SubmitRequest

from control_plane.scheduler.client import SchedulerClient
from control_plane.scheduler.types import SchedulingResult, SchedulingStatus, SubmitAck


class StubSchedulerClient:
    """Contract placeholder until services/scheduler exists."""

    async def submit_request(self, submit: SubmitRequest) -> SubmitAck:
        return SubmitAck(
            request_id=submit.inference_request.request_id,
            status=SchedulingStatus.NOT_SUBMITTED,
            message="scheduler not connected",
        )

    async def get_scheduling_status(self, request_id: UUID) -> SchedulingStatus:
        return SchedulingStatus.NOT_SUBMITTED

    async def receive_scheduling_result(self, request_id: UUID) -> SchedulingResult | None:
        return None
