"""OpenAI SSE formatting. Owner: api_gateway.streaming."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from gpu_inference_observability.streaming.models import StreamChunk


def format_sse_data(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, separators=(',', ':'))}\n\n"


def format_sse_done() -> str:
    return "data: [DONE]\n\n"


def chunk_to_openai_sse(
    chunk: StreamChunk,
    *,
    model: str,
    created: int | None = None,
    include_role: bool = False,
) -> str:
    created_at = created or int(chunk.timestamp.timestamp())
    delta: dict[str, Any] = {}
    if include_role and chunk.is_first:
        delta["role"] = "assistant"
    if chunk.delta_text:
        delta["content"] = chunk.delta_text
    payload = {
        "id": str(chunk.request_id),
        "object": "chat.completion.chunk",
        "created": created_at,
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": delta,
                "finish_reason": chunk.finish_reason,
            }
        ],
    }
    return format_sse_data(payload)


def format_stream_error_sse(message: str, *, request_id: str, model: str) -> str:
    payload = {
        "id": request_id,
        "object": "chat.completion.chunk",
        "created": int(datetime.now(timezone.utc).timestamp()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": {"content": ""},
                "finish_reason": "error",
            }
        ],
        "error": message,
    }
    return format_sse_data(payload)
