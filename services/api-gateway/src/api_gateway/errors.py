"""OpenAI-compatible error responses."""

from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from common_schemas.states import FailureReason


class ErrorBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    message: str
    code: str
    param: str | None = None
    retry_after_ms: int | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


class GatewayError(Exception):
    def __init__(
        self,
        *,
        error_type: FailureReason | str,
        message: str,
        status_code: int,
        param: str | None = None,
        retry_after_ms: int | None = None,
    ) -> None:
        self.error_type = str(error_type)
        self.message = message
        self.status_code = status_code
        self.param = param
        self.retry_after_ms = retry_after_ms
        super().__init__(message)


def error_response(exc: GatewayError) -> JSONResponse:
    body = ErrorResponse(
        error=ErrorBody(
            type=exc.error_type,
            message=exc.message,
            code=exc.error_type,
            param=exc.param,
            retry_after_ms=exc.retry_after_ms,
        )
    )
    headers: dict[str, str] = {}
    if exc.retry_after_ms is not None:
        headers["Retry-After"] = str(max(1, exc.retry_after_ms // 1000))
    return JSONResponse(status_code=exc.status_code, content=body.model_dump(), headers=headers)


async def gateway_error_handler(_request: Request, exc: GatewayError) -> JSONResponse:
    return error_response(exc)


async def unhandled_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    if isinstance(exc, GatewayError):
        return error_response(exc)
    return error_response(
        GatewayError(
            error_type=FailureReason.INTERNAL_ERROR,
            message="internal gateway error",
            status_code=500,
        )
    )


def validation_error(message: str, param: str | None = None) -> GatewayError:
    return GatewayError(
        error_type=FailureReason.VALIDATION_ERROR,
        message=message,
        status_code=400,
        param=param,
    )


def unsupported_field(field: str) -> GatewayError:
    return GatewayError(
        error_type=FailureReason.UNSUPPORTED_FIELD,
        message=f"unsupported field: {field}",
        status_code=400,
        param=field,
    )


def unknown_model(model: str) -> GatewayError:
    return GatewayError(
        error_type=FailureReason.UNKNOWN_MODEL,
        message=f"unknown model: {model}",
        status_code=404,
    )


def authentication_error(message: str = "invalid or missing API key") -> GatewayError:
    return GatewayError(
        error_type=FailureReason.AUTHENTICATION_ERROR,
        message=message,
        status_code=401,
    )


def not_implemented(message: str) -> GatewayError:
    return GatewayError(
        error_type=FailureReason.INTERNAL_ERROR,
        message=message,
        status_code=501,
    )
