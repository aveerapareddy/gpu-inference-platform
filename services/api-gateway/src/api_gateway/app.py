"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from gpu_inference_observability import StructuredLogger

from api_gateway.config import Settings, get_settings
from api_gateway.dependencies import (
    get_control_plane_client,
    get_logger,
    shutdown_control_plane,
    startup_control_plane,
)
from api_gateway.errors import GatewayError, gateway_error_handler, unhandled_error_handler
from api_gateway.middleware import RequestTimingMiddleware
from api_gateway.routers import completions, health, metrics


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = app.state.settings
    logger: StructuredLogger = app.state.logger
    logger.info("gateway starting", gateway_instance_id=settings.gateway_instance_id)
    await startup_control_plane()
    control_plane = get_control_plane_client()
    app.state.control_plane = control_plane
    ready = await control_plane.is_ready()
    logger.info("control plane probe", ready=ready)
    yield
    await shutdown_control_plane()
    logger.info("gateway shutdown")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    logger = get_logger()

    app = FastAPI(
        title="GPU Inference Platform API Gateway",
        version="0.1.0",
        description="Session 13: Prometheus /metrics export on embedded stack.",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.logger = logger

    app.add_middleware(RequestTimingMiddleware, settings=settings, logger=logger)
    app.add_exception_handler(GatewayError, gateway_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)

    app.include_router(health.router)
    app.include_router(completions.router)
    app.include_router(metrics.router)

    return app
