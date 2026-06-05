"""SubmitRequest builder for replay payloads."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from common_schemas.inference_request import InferenceRequest, RequestContext, SubmitRequest

from gpu_inference_observability.runtime.replay.models import RequestPayloadSnapshot


def submit_from_payload(snapshot: RequestPayloadSnapshot) -> SubmitRequest:
    return SubmitRequest(
        inference_request=InferenceRequest.model_validate(snapshot.inference_request),
        request_context=RequestContext.model_validate(snapshot.request_context),
    )


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
