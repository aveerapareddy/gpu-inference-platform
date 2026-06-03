"""Prometheus metrics export."""

from __future__ import annotations

from fastapi import APIRouter, Response

from api_gateway.dependencies import get_metrics_registry
from gpu_inference_observability.registry.registry import CONTENT_TYPE_LATEST

router = APIRouter(tags=["metrics"])


@router.get("/metrics")
async def prometheus_metrics() -> Response:
    registry = get_metrics_registry()
    if registry is None:
        return Response(content=b"", media_type=CONTENT_TYPE_LATEST)
    return Response(content=registry.export_prometheus(), media_type=CONTENT_TYPE_LATEST)
