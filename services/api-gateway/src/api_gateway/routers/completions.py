"""Inference API endpoints (validation + placeholder response)."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Header, Request, Response
from fastapi.responses import StreamingResponse
from gpu_inference_observability import LogContext, StructuredLogger

from api_gateway.config import Settings
from api_gateway.control_plane.client import ControlPlaneClient
from api_gateway.dependencies import (
    get_app_settings,
    get_control_plane_client,
    get_logger,
    get_platform_stack,
    read_raw_body,
)
from api_gateway.pipeline import (
    placeholder_chat_response,
    placeholder_text_completion_response,
    process_chat_completion,
    process_streaming_chat_completion,
)
from api_gateway.runtime.stack import PlatformStack
from api_gateway.streaming.engine import StreamEngine

router = APIRouter(prefix="/v1", tags=["inference"])


def _stream_engine(stack: PlatformStack) -> StreamEngine:
    return StreamEngine(stack, stream_events=stack.stream_events)


@router.post("/chat/completions")
async def create_chat_completion(
    request: Request,
    response: Response,
    raw_body: bytes = Depends(read_raw_body),
    authorization: str | None = Header(default=None),
    x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
    x_request_id: str | None = Header(default=None, alias="X-Request-Id"),
    settings: Settings = Depends(get_app_settings),
    control_plane: ControlPlaneClient = Depends(get_control_plane_client),
    logger: StructuredLogger = Depends(get_logger),
    stack: PlatformStack | None = Depends(get_platform_stack),
) -> dict | StreamingResponse:
    started = time.perf_counter()
    body_stream = _request_wants_stream(raw_body)
    if body_stream and settings.full_path_integrated and stack is not None:
        ctx, submit, session, validation_ms = await process_streaming_chat_completion(
            raw_body=raw_body,
            authorization=authorization,
            correlation_header=x_correlation_id,
            client_request_header=x_request_id,
            settings=settings,
            control_plane=control_plane,
            logger=logger,
            is_legacy_completion=False,
        )
        engine = _stream_engine(stack)

        async def sse_generator() -> AsyncIterator[str]:
            async for event in engine.stream_sse(
                session,
                submit,
                disconnect_check=request.is_disconnected,
            ):
                yield event

        headers = {
            "X-Request-Id": str(ctx.request_id),
            "X-Correlation-Id": ctx.correlation_id,
            "X-Stream-Id": str(session.stream_id),
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
        log_ctx = LogContext(
            service=settings.service_name,
            request_id=ctx.request_id,
            trace_id=ctx.correlation_id,
            model=ctx.requested_model,
        )
        logger.info(
            "streaming response started",
            ctx=log_ctx,
            validation_ms=round(validation_ms, 3),
            stream_id=str(session.stream_id),
        )
        return StreamingResponse(sse_generator(), media_type="text/event-stream", headers=headers)

    ctx, validation_ms = await process_chat_completion(
        raw_body=raw_body,
        authorization=authorization,
        correlation_header=x_correlation_id,
        client_request_header=x_request_id,
        settings=settings,
        control_plane=control_plane,
        logger=logger,
        is_legacy_completion=False,
    )
    response.headers["X-Request-Id"] = str(ctx.request_id)
    response.headers["X-Correlation-Id"] = ctx.correlation_id

    log_ctx = LogContext(
        service=settings.service_name,
        request_id=ctx.request_id,
        trace_id=ctx.correlation_id,
        model=ctx.requested_model,
    )
    total_ms = (time.perf_counter() - started) * 1000.0
    logger.info(
        "placeholder response sent",
        ctx=log_ctx,
        validation_ms=round(validation_ms, 3),
        total_ms=round(total_ms, 3),
    )
    return placeholder_chat_response(ctx)


def _request_wants_stream(raw_body: bytes) -> bool:
    import json

    try:
        data = json.loads(raw_body)
    except json.JSONDecodeError:
        return False
    return bool(data.get("stream"))


@router.post("/completions")
async def create_completion(
    response: Response,
    raw_body: bytes = Depends(read_raw_body),
    authorization: str | None = Header(default=None),
    x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
    x_request_id: str | None = Header(default=None, alias="X-Request-Id"),
    settings: Settings = Depends(get_app_settings),
    control_plane: ControlPlaneClient = Depends(get_control_plane_client),
    logger: StructuredLogger = Depends(get_logger),
) -> dict:
    ctx, _validation_ms = await process_chat_completion(
        raw_body=raw_body,
        authorization=authorization,
        correlation_header=x_correlation_id,
        client_request_header=x_request_id,
        settings=settings,
        control_plane=control_plane,
        logger=logger,
        is_legacy_completion=True,
    )
    response.headers["X-Request-Id"] = str(ctx.request_id)
    response.headers["X-Correlation-Id"] = ctx.correlation_id
    return placeholder_text_completion_response(ctx)
