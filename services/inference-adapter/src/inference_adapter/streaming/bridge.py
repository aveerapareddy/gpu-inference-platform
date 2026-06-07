"""Adapter streaming bridge. Owner: inference adapter."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from gpu_inference_observability.streaming.models import StreamChunk


async def stream_inference_request(
    backend: Any,
    *,
    request_id: UUID,
    stream_id: UUID,
    inference_request: Any,
    model: str,
    batch_id: UUID | None = None,
) -> AsyncIterator[StreamChunk]:
    if hasattr(backend, "stream_request"):
        async for chunk in backend.stream_request(
            request_id=request_id,
            stream_id=stream_id,
            inference_request=inference_request,
            model=model,
            batch_id=batch_id,
        ):
            yield chunk
        return
    text = "mock stream token"
    for index, token in enumerate(text.split()):
        yield StreamChunk(
            stream_id=stream_id,
            request_id=request_id,
            index=index,
            delta_text=token if index == 0 else f" {token}",
            finish_reason=None,
            timestamp=datetime.now(timezone.utc),
            is_first=index == 0,
        )
    yield StreamChunk(
        stream_id=stream_id,
        request_id=request_id,
        index=len(text.split()),
        delta_text="",
        finish_reason="stop",
        timestamp=datetime.now(timezone.utc),
        is_first=False,
    )
