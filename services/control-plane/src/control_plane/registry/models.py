"""Registered request record."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from common_schemas.inference_request import InferenceRequest, RequestContext, SubmitRequest
from common_schemas.states import FailureReason, RequestState


@dataclass
class RegisteredRequest:
    submit: SubmitRequest
    state: RequestState
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    failure_reason: FailureReason | None = None
    failure_message: str | None = None
    queue_entered_at: datetime | None = None
    queue_position: int | None = None

    @property
    def request_id(self):
        return self.submit.inference_request.request_id

    @property
    def inference_request(self) -> InferenceRequest:
        return self.submit.inference_request

    @property
    def request_context(self) -> RequestContext:
        return self.submit.request_context
