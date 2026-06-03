"""Dependency wiring for FastAPI application."""

from __future__ import annotations

from functools import lru_cache

from fastapi import Request
from gpu_inference_observability import StructuredLogger

from api_gateway.config import Settings, get_settings
from api_gateway.control_plane.client import ControlPlaneClient
from api_gateway.control_plane.integrated import IntegratedControlPlaneClient
from api_gateway.control_plane.stub import StubControlPlaneClient
from api_gateway.runtime.integrated_client import IntegratedPlatformClient
from api_gateway.runtime.stack import PlatformStack, create_platform_stack
from control_plane.application import ControlPlaneApplication, create_application

_stack: PlatformStack | None = None
_cp_app: ControlPlaneApplication | None = None


def _get_control_plane_application() -> ControlPlaneApplication:
    global _cp_app
    if _cp_app is None:
        _cp_app = create_application()
    return _cp_app


def _get_platform_stack() -> PlatformStack:
    global _stack
    if _stack is None:
        _stack = create_platform_stack()
    return _stack


async def startup_control_plane() -> None:
    settings = get_settings()
    if settings.full_path_integrated:
        stack = _get_platform_stack()
        if not stack.control_plane.is_running:
            await stack.startup()
        return
    app = _get_control_plane_application()
    if not app.is_running:
        await app.startup()


async def shutdown_control_plane() -> None:
    global _stack, _cp_app
    settings = get_settings()
    if settings.full_path_integrated and _stack is not None:
        if _stack.control_plane.is_running:
            await _stack.shutdown()
        _stack = None
        return
    if _cp_app is not None and _cp_app.is_running:
        await _cp_app.shutdown()


@lru_cache
def get_logger() -> StructuredLogger:
    settings = get_settings()
    return StructuredLogger(settings.service_name)


def get_control_plane_client() -> ControlPlaneClient:
    settings = get_settings()
    if settings.full_path_integrated:
        return IntegratedPlatformClient(_get_platform_stack())
    if settings.control_plane_integrated:
        return IntegratedControlPlaneClient(_get_control_plane_application())
    return StubControlPlaneClient()


def get_app_settings() -> Settings:
    return get_settings()


async def read_raw_body(request: Request) -> bytes:
    return await request.body()
