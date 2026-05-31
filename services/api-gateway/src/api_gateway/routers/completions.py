"""Inference API endpoints (validation + placeholder response)."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, Header, Response
from gpu_inference_observability import LogContext, StructuredLogger

from api_gateway.config import Settings
from api_gateway.control_plane.client import ControlPlaneClient
from api_gateway.dependencies import (
    get_app_settings,
    get_control_plane_client,
    get_logger,
    read_raw_body,
)
from api_gateway.pipeline import (
    placeholder_chat_response,
    placeholder_text_completion_response,
    process_chat_completion,
)

router = APIRouter(prefix="/v1", tags=["inference"])


@router.post("/chat/completions")
async def create_chat_completion(
    response: Response,
    raw_body: bytes = Depends(read_raw_body),
    authorization: str | None = Header(default=None),
    x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
    x_request_id: str | None = Header(default=None, alias="X-Request-Id"),
    settings: Settings = Depends(get_app_settings),
    control_plane: ControlPlaneClient = Depends(get_control_plane_client),
    logger: StructuredLogger = Depends(get_logger),
) -> dict:
    started = time.perf_counter()
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
