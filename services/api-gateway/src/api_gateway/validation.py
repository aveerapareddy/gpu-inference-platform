"""Request validation and normalization."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID, uuid4

from common_schemas.inference_request import InferenceRequest, Message, ModelRecord
from common_schemas.states import MessageRole
from pydantic import ValidationError

from api_gateway.config import Settings
from api_gateway.errors import (
    GatewayError,
    authentication_error,
    not_implemented,
    unknown_model,
    validation_error,
)
from api_gateway.schemas.openai import (
    ALLOWED_CHAT_FIELDS,
    ALLOWED_COMPLETION_FIELDS,
    ChatCompletionRequestIn,
    ChatMessageIn,
    CompletionRequestIn,
    check_unsupported_fields,
)


def parse_json_body(raw: bytes, max_bytes: int) -> dict[str, Any]:
    if len(raw) > max_bytes:
        raise validation_error(
            f"request body exceeds maximum size of {max_bytes} bytes",
            param="body",
        )
    if not raw:
        raise validation_error("request body is required", param="body")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise validation_error(f"invalid JSON: {exc}", param="body") from exc
    if not isinstance(data, dict):
        raise validation_error("request body must be a JSON object", param="body")
    return data


def validate_api_key(authorization: str | None, settings: Settings) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise authentication_error()
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise authentication_error()
    if settings.api_keys:
        allowed = {k.strip() for k in settings.api_keys.split(",") if k.strip()}
        if token not in allowed:
            raise authentication_error()
    return token


def validate_prompt_length(messages: list[Message], max_chars: int) -> None:
    total = sum(len(m.content) for m in messages)
    if total > max_chars:
        raise validation_error(
            f"total prompt length {total} exceeds limit {max_chars}",
            param="messages",
        )


def parse_chat_request(body: dict[str, Any]) -> ChatCompletionRequestIn:
    check_unsupported_fields(body, ALLOWED_CHAT_FIELDS)
    try:
        return ChatCompletionRequestIn.model_validate(body)
    except ValidationError as exc:
        raise _pydantic_to_gateway(exc) from exc


def parse_completion_request(body: dict[str, Any]) -> ChatCompletionRequestIn:
    check_unsupported_fields(body, ALLOWED_COMPLETION_FIELDS)
    try:
        completion = CompletionRequestIn.model_validate(body)
    except ValidationError as exc:
        raise _pydantic_to_gateway(exc) from exc
    return ChatCompletionRequestIn(
        model=completion.model,
        messages=[ChatMessageIn(role=MessageRole.USER, content=completion.prompt)],
        stream=completion.stream,
        max_tokens=completion.max_tokens,
        temperature=completion.temperature,
        top_p=completion.top_p,
    )


def _pydantic_to_gateway(exc: ValidationError) -> GatewayError:
    errors = exc.errors()
    if not errors:
        return validation_error("invalid request")
    first = errors[0]
    loc = first.get("loc", ())
    param = ".".join(str(part) for part in loc) if loc else None
    msg = first.get("msg", "invalid request")
    return validation_error(str(msg), param=param)


def ensure_streaming_not_requested(stream: bool) -> None:
    if stream:
        raise not_implemented("streaming is not implemented; set stream=false")


def resolve_model_record(model_id: str, record: ModelRecord | None) -> ModelRecord:
    if record is None:
        raise unknown_model(model_id)
    return record


def build_inference_request(
    parsed: ChatCompletionRequestIn,
    *,
    request_id: UUID,
    model_record: ModelRecord,
    settings: Settings,
    api_key_id: str,
    client_request_id: str | None,
) -> InferenceRequest:
    max_tokens = parsed.max_tokens or min(
        settings.default_max_tokens,
        model_record.max_output_tokens,
    )
    if max_tokens > model_record.max_output_tokens:
        raise validation_error(
            f"max_tokens exceeds model limit {model_record.max_output_tokens}",
            param="max_tokens",
        )

    messages = [
        Message(role=m.role, content=m.content)
        for m in parsed.messages
    ]
    validate_prompt_length(messages, model_record.max_prompt_tokens)

    return InferenceRequest(
        request_id=request_id,
        model=model_record.model_id,
        messages=messages,
        stream=parsed.stream,
        max_tokens=max_tokens,
        temperature=parsed.temperature,
        top_p=parsed.top_p,
        api_key_id=api_key_id,
        client_request_id=client_request_id,
    )


def new_request_id() -> UUID:
    return uuid4()
