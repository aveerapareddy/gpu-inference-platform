"""SubmitRequest builder for replay payloads."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from common_schemas.inference_request import InferenceRequest, RequestContext, SubmitRequest
from common_schemas.states import MessageRole, PriorityClass

from gpu_inference_observability.runtime.replay.models import RequestPayloadSnapshot


def submit_from_payload(snapshot: RequestPayloadSnapshot) -> SubmitRequest:
    normalized = normalize_payload_snapshot(snapshot)
    return SubmitRequest(
        inference_request=InferenceRequest.model_validate(normalized.inference_request),
        request_context=RequestContext.model_validate(normalized.request_context),
    )


def normalize_payload_snapshot(snapshot: RequestPayloadSnapshot) -> RequestPayloadSnapshot:
    """Coerce JSON-deserialized payload fields for strict Pydantic validation."""
    inference_request = _coerce_inference_request(dict(snapshot.inference_request))
    request_context = _coerce_request_context(dict(snapshot.request_context))
    return RequestPayloadSnapshot(
        inference_request=inference_request,
        request_context=request_context,
    )


def _coerce_inference_request(data: dict[str, Any]) -> dict[str, Any]:
    if isinstance(data.get("request_id"), str):
        data["request_id"] = UUID(data["request_id"])
    messages = data.get("messages") or []
    for message in messages:
        role = message.get("role")
        if isinstance(role, str):
            message["role"] = MessageRole(role)
    priority = data.get("priority_class")
    if isinstance(priority, str):
        data["priority_class"] = PriorityClass(priority)
    return data


def _coerce_request_context(data: dict[str, Any]) -> dict[str, Any]:
    if isinstance(data.get("request_id"), str):
        data["request_id"] = UUID(data["request_id"])
    arrival = data.get("arrival_time")
    if isinstance(arrival, str):
        data["arrival_time"] = datetime.fromisoformat(arrival)
    return data


def submit_from_payload_with_replay_id(
    snapshot: RequestPayloadSnapshot,
    replay_id: UUID,
) -> SubmitRequest:
    submit = submit_from_payload(snapshot)
    return SubmitRequest(
        inference_request=InferenceRequest(
            **{
                **submit.inference_request.model_dump(),
                "request_id": replay_id,
            }
        ),
        request_context=RequestContext(
            **{
                **submit.request_context.model_dump(),
                "request_id": replay_id,
                "trace_id": f"replay-{replay_id}",
                "span_id": f"replay-span-{replay_id}",
                "arrival_time": datetime.now(submit.request_context.arrival_time.tzinfo),
            }
        ),
    )
