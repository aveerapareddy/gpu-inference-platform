"""Gateway stream engine. Owner: api_gateway.streaming."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from common_schemas.inference_request import SubmitRequest
from common_schemas.states import RequestState
from common_schemas.streaming import StreamingMetricsRecord
from gpu_inference_observability.registry.recorder import RuntimeMetricsRecorder
from gpu_inference_observability.streaming.events import StreamEventEmitter, StreamEventType
from gpu_inference_observability.streaming.models import (
    StreamChunk,
    StreamLifecycleState,
    StreamResult,
    StreamSession,
)

from api_gateway.runtime.orchestrator import RequestPathOrchestrator
from api_gateway.runtime.stack import PlatformStack
from api_gateway.streaming.sse import chunk_to_openai_sse, format_sse_done, format_stream_error_sse


class StreamEngine:
    """Owns token delivery from backend stream to SSE transport."""

    def __init__(
        self,
        stack: PlatformStack,
        *,
        stream_events: StreamEventEmitter | None = None,
        metrics_recorder: RuntimeMetricsRecorder | None = None,
    ) -> None:
        self._stack = stack
        self._orchestrator = RequestPathOrchestrator(stack)
        self._events = stream_events
        self._metrics = metrics_recorder or stack.metrics_recorder
        self._cancelled_streams: set[UUID] = set()

    def cancel_stream(self, stream_id: UUID) -> None:
        self._cancelled_streams.add(stream_id)

    async def stream_sse(
        self,
        session: StreamSession,
        submit: SubmitRequest,
        *,
        disconnect_check: Any | None = None,
    ) -> AsyncIterator[str]:
        if self._metrics is not None:
            self._metrics.record_stream_created()
        self._emit(StreamEventType.STREAM_CREATED, session)
        session.state = StreamLifecycleState.STREAM_CREATED
        created = int(session.context.request_received_time.timestamp())
        role_sent = False
        previous_token_time: datetime | None = None

        try:
            async for chunk in self._orchestrator.execute_streaming_path(submit, session):
                if stream_id_cancelled(session, self._cancelled_streams):
                    await self._handle_cancel(session, submit)
                    return
                if disconnect_check is not None and await disconnect_check():
                    await self._handle_cancel(session, submit)
                    return

                include_role = not role_sent and chunk.is_first
                if include_role:
                    role_sent = True
                yield chunk_to_openai_sse(
                    chunk,
                    model=submit.inference_request.model,
                    created=created,
                    include_role=include_role,
                )

                now = chunk.timestamp
                if chunk.is_first or (chunk.delta_text and session.token_count == 0):
                    session.timing.record_token(now)
                    session.state = StreamLifecycleState.STREAM_ACTIVE
                    self._emit(StreamEventType.FIRST_TOKEN_EMITTED, session, extra={"index": chunk.index})
                    if self._metrics is not None and session.timing.ttft_ms is not None:
                        self._metrics.record_ttft(session.timing.ttft_ms / 1000.0)
                elif chunk.delta_text:
                    session.timing.record_token(now)
                    if previous_token_time is not None and self._metrics is not None:
                        itl = (now - previous_token_time).total_seconds()
                        self._metrics.record_itl(itl)
                    self._emit(
                        StreamEventType.TOKEN_EMITTED,
                        session,
                        extra={"index": chunk.index, "delta_length": len(chunk.delta_text)},
                    )
                if chunk.delta_text:
                    previous_token_time = now
                    session.generated_text += chunk.delta_text
                    session.token_count += 1

                if chunk.finish_reason:
                    session.timing.completion_time = now
                    session.state = StreamLifecycleState.STREAM_COMPLETED
                    self._emit(StreamEventType.STREAM_COMPLETED, session)
                    if self._metrics is not None:
                        self._metrics.record_stream_completed()

            yield format_sse_done()
            await self._persist_stream_result(session, submit)
        except Exception as exc:
            session.state = StreamLifecycleState.STREAM_FAILED
            session.error = str(exc)
            session.timing.completion_time = datetime.now(timezone.utc)
            self._emit(StreamEventType.STREAM_FAILED, session, extra={"error": str(exc)})
            if self._metrics is not None:
                self._metrics.record_stream_failed()
            yield format_stream_error_sse(str(exc), request_id=str(session.request_id), model=submit.inference_request.model)
            yield format_sse_done()
            await self._persist_stream_failure(session, submit, str(exc))

    async def _handle_cancel(self, session: StreamSession, submit: SubmitRequest) -> None:
        session.state = StreamLifecycleState.STREAM_CANCELLED
        session.timing.completion_time = datetime.now(timezone.utc)
        self._emit(StreamEventType.STREAM_CANCELLED, session)
        if self._metrics is not None:
            self._metrics.record_stream_cancelled()
        if session.context.backend_id is not None:
            await self._stack.adapter.cancel_request(
                session.request_id,
                backend_id=session.context.backend_id,
            )
        entry = self._stack.control_plane.lifecycle.get_entry(session.request_id)
        if entry.state in {RequestState.STREAMING, RequestState.SUBMITTED}:
            self._stack.control_plane.lifecycle.transition(session.request_id, RequestState.CANCELLED)
        await self._persist_stream_metrics(session, submit)

    async def _persist_stream_result(self, session: StreamSession, submit: SubmitRequest) -> None:
        await self._persist_stream_metrics(session, submit)

    async def _persist_stream_metrics(self, session: StreamSession, submit: SubmitRequest) -> None:
        result = StreamResult.from_session(session)
        metrics = StreamingMetricsRecord(
            stream_id=result.stream_id,
            request_id=result.request_id,
            ttft_ms=result.ttft_ms,
            itl_ms_p50=result.itl_ms_p50,
            itl_ms_p99=result.itl_ms_p99,
            token_count=result.token_count,
            generated_text=result.generated_text,
            completed_at=result.completion_time,
            stream_state=result.state.value,
        )
        entry = self._stack.control_plane.lifecycle.get_entry(session.request_id)
        entry.stream_metrics = metrics
        if self._stack.replay_engine is not None:
            self._stack.replay_engine.capture_from_entry(entry)

    async def _persist_stream_failure(self, session: StreamSession, submit: SubmitRequest, error: str) -> None:
        entry = self._stack.control_plane.lifecycle.get_entry(session.request_id)
        if entry.state.value not in {"failed", "cancelled"}:
            from common_schemas.states import FailureReason

            self._stack.control_plane.lifecycle.mark_failed(
                session.request_id,
                FailureReason.ADAPTER_ERROR,
                error,
            )
            entry = self._stack.control_plane.lifecycle.get_entry(session.request_id)
        if self._stack.replay_engine is not None:
            self._stack.replay_engine.capture_from_entry(entry)

    def _emit(self, event_type: StreamEventType, session: StreamSession, *, extra: dict | None = None) -> None:
        if self._events is None:
            return
        self._events.emit(
            event_type,
            request_id=session.request_id,
            stream_id=session.stream_id,
            extra=extra,
        )


def stream_id_cancelled(session: StreamSession, cancelled: set[UUID]) -> bool:
    return session.stream_id in cancelled
