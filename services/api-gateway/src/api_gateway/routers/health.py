"""Operational endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api_gateway import __version__
from api_gateway.config import Settings
from api_gateway.control_plane.client import ControlPlaneClient
from api_gateway.dependencies import get_app_settings, get_control_plane_client

router = APIRouter(tags=["operations"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def ready(
    control_plane: ControlPlaneClient = Depends(get_control_plane_client),
) -> JSONResponse:
    if await control_plane.is_ready():
        return JSONResponse(status_code=200, content={"status": "ready"})
    return JSONResponse(
        status_code=503,
        content={"status": "not_ready", "reason": "control_plane_unavailable"},
    )


@router.get("/version")
async def version(settings: Settings = Depends(get_app_settings)) -> dict[str, str]:
    return {
        "service": settings.service_name,
        "version": __version__,
        "gateway_instance_id": settings.gateway_instance_id,
    }
