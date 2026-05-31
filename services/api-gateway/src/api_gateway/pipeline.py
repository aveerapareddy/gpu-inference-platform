"""Validate requests and build gateway context. No scheduler or inference."""

from __future__ import annotations

import hashlib
import time
from typing import Any

from gpu_inference_observability import LogContext, StructuredLogger

from api_gateway.config import Settings
from api_gateway.context import GatewayRequestContext, build_request_context
from api_gateway.control_plane.client import ControlPlaneClient
from api_gateway.schemas.openai import ChatCompletionRequestIn
from api_gateway.validation import (
    build_inference_request,
    ensure_streaming_not_requested,
    new_request_id,
    parse_chat_request,
    parse_completion_request,
    parse_json_body,
    resolve_model_record,
    validate_api_key,
)


def _api_key_id(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()[:16]


async def process_chat_completion(
    *,
    raw_body: bytes,
    authorization: str | None,
    correlation_header: str | None,
    client_request_header: str | None,
    settings: Settings,
    control_plane: ControlPlaneClient,
    logger: StructuredLogger,
    is_legacy_completion: bool = False,
) -> tuple[GatewayRequestContext, float]:
    """Returns validated context and validation duration in milliseconds."""
    started = time.perf_counter()
    token = validate_api_key(authorization, settings)
    body = parse_json_body(raw_body, settings.max_body_bytes)

    if is_legacy_completion:
        parsed = parse_completion_request(body)
    else:
        parsed = parse_chat_request(body)

    ensure_streaming_not_requested(parsed.stream)

    request_id = new_request_id()
    model_record = resolve_model_record(
        parsed.model,
        await control_plane.get_model(parsed.model),
    )

    inference_request = build_inference_request(
        parsed,
        request_id=request_id,
        model_record=model_record,
        settings=settings,
        api_key_id=_api_key_id(token),
        client_request_id=client_request_header,
    )

    correlation_id = (correlation_header or client_request_header or "").strip()
    ctx = build_request_context(
        inference_request=inference_request,
        settings=settings,
        correlation_id=correlation_id,
    )

    elapsed_ms = (time.perf_counter() - started) * 1000.0
    log_ctx = LogContext(
        service=settings.service_name,
        request_id=ctx.request_id,
        trace_id=ctx.correlation_id,
        span_id=ctx.request_context.span_id,
        model=ctx.requested_model,
    )
    logger.info(
        "request validated",
        ctx=log_ctx,
        validation_ms=round(elapsed_ms, 3),
        message_count=len(inference_request.messages),
    )
    return ctx, elapsed_ms


def placeholder_chat_response(ctx: GatewayRequestContext) -> dict[str, Any]:
    """Contract-shaped response; inference path not connected."""
    created = int(ctx.received_timestamp.timestamp())
    return {
        "id": str(ctx.request_id),
        "object": "chat.completion",
        "created": created,
        "model": ctx.inference_request.model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": (
                        "Gateway validation complete. "
                        "Scheduler and inference are not connected in Session 4."
                    ),
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        },
    }


def placeholder_text_completion_response(ctx: GatewayRequestContext) -> dict[str, Any]:
    created = int(ctx.received_timestamp.timestamp())
    return {
        "id": str(ctx.request_id),
        "object": "text_completion",
        "created": created,
        "model": ctx.inference_request.model,
        "choices": [
            {
                "index": 0,
                "text": (
                    "Gateway validation complete. "
                    "Scheduler and inference are not connected in Session 4."
                ),
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        },
    }
