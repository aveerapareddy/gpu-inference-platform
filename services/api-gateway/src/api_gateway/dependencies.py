"""FastAPI dependencies."""

from __future__ import annotations

from functools import lru_cache

from fastapi import Request
from gpu_inference_observability import StructuredLogger

from api_gateway.config import Settings, get_settings
from api_gateway.control_plane.client import ControlPlaneClient
from api_gateway.control_plane.stub import StubControlPlaneClient


@lru_cache
def get_logger() -> StructuredLogger:
    settings = get_settings()
    return StructuredLogger(settings.service_name)


@lru_cache
def get_control_plane_client() -> ControlPlaneClient:
    settings = get_settings()
    if settings.control_plane_stub_enabled:
        return StubControlPlaneClient()
    return StubControlPlaneClient()


def get_app_settings() -> Settings:
    return get_settings()


async def read_raw_body(request: Request) -> bytes:
    return await request.body()
