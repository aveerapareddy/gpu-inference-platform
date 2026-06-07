#!/usr/bin/env python3
"""Session 19 streaming validation. Run: python runtime-validation/stream_validation.py"""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
for rel in (
    "packages/common-schemas/src",
    "packages/observability/src",
    "services/api-gateway/src",
    "services/control-plane/src",
    "services/scheduler/src",
    "services/inference-adapter/src",
):
    path = str(ROOT / rel)
    if path not in sys.path:
        sys.path.insert(0, path)

from common_schemas.inference_request import InferenceRequest, Message, RequestContext, SubmitRequest
from common_schemas.states import MessageRole, RequestState
from gpu_inference_observability import StructuredLogger
from gpu_inference_observability.registry.registry import PROMETHEUS_PREFIX
from gpu_inference_observability.streaming.events import StreamEventEmitter, StreamEventType
from gpu_inference_observability.streaming.models import StreamLifecycleState, StreamSession
from inference_adapter.backends.mock import MockInferenceBackend

from api_gateway.streaming.engine import StreamEngine
from harness import ValidationStack, metric_value, submit_request


def stream_submit(model: str = "demo") -> SubmitRequest:
    rid = uuid4()
    return SubmitRequest(
        inference_request=InferenceRequest(
            request_id=rid,
            model=model,
            messages=[Message(role=MessageRole.USER, content="stream validation")],
            stream=True,
            max_tokens=16,
        ),
        request_context=RequestContext(
            request_id=rid,
            trace_id=f"trace-{rid}",
            span_id="span",
            arrival_time=datetime.now(timezone.utc),
            model=model,
            stream=True,
            gateway_instance_id="validation",
        ),
    )


def _stack_with_stream_events(backend: MockInferenceBackend | None = None) -> ValidationStack:
    stack = ValidationStack(backend=backend or MockInferenceBackend())
    stack.stack.stream_events = StreamEventEmitter(
        StructuredLogger("streaming"),
        trace_recorder=stack.trace_recorder,
    )
    return stack


async def scenario_successful_streaming() -> None:
    stack = _stack_with_stream_events()
    await stack.startup()
    submit = stream_submit()
    entry = await stack.orchestrator.lifecycle.process_through_queued(submit)
    assert entry.state == RequestState.QUEUED

    session = StreamSession.create(
        request_id=submit.inference_request.request_id,
        correlation_id=submit.request_context.trace_id,
        model=submit.inference_request.model,
    )
    engine = StreamEngine(stack.stack, stream_events=stack.stack.stream_events)
    events: list[str] = []
    async for sse in engine.stream_sse(session, submit):
        events.append(sse)

    assert any("chat.completion.chunk" in e for e in events)
    assert any("[DONE]" in e for e in events)
    final = stack.cp.lifecycle.get_entry(submit.inference_request.request_id)
    assert final.state == RequestState.COMPLETED
    assert final.stream_metrics is not None
    assert final.stream_metrics.ttft_ms is not None
    assert final.stream_metrics.token_count >= 1
    assert final.stream_metrics.generated_text

    timeline = stack.trace_inspector.get_request_timeline(submit.inference_request.request_id)
    stream_event_types = {e.event_type for e in timeline.events if e.extra.get("stream_event")}
    assert StreamEventType.STREAM_CREATED.value in stream_event_types
    assert StreamEventType.FIRST_TOKEN_EMITTED.value in stream_event_types
    assert StreamEventType.STREAM_COMPLETED.value in stream_event_types

    export = stack.metrics_export()
    assert metric_value(export, f"{PROMETHEUS_PREFIX}_streams_created_total") >= 1.0
    assert metric_value(export, f"{PROMETHEUS_PREFIX}_streams_completed_total") >= 1.0
    assert metric_value(export, f"{PROMETHEUS_PREFIX}_request_ttft_seconds") >= 0.0

    record = stack.replay_engine.execution_store.get(submit.inference_request.request_id)
    assert record is not None
    assert record.stream_metrics is not None
    await stack.shutdown()


async def scenario_stream_cancellation() -> None:
    backend = MockInferenceBackend()
    stack = _stack_with_stream_events(backend)
    await stack.startup()
    submit = stream_submit()
    await stack.orchestrator.lifecycle.process_through_queued(submit)
    session = StreamSession.create(
        request_id=submit.inference_request.request_id,
        correlation_id=submit.request_context.trace_id,
        model=submit.inference_request.model,
    )
    engine = StreamEngine(stack.stack, stream_events=stack.stack.stream_events)

    collected: list[str] = []
    async for sse in engine.stream_sse(session, submit):
        collected.append(sse)
        if len(collected) >= 2:
            engine.cancel_stream(session.stream_id)

    entry = stack.cp.lifecycle.get_entry(submit.inference_request.request_id)
    assert entry.state == RequestState.CANCELLED
    assert entry.stream_metrics is not None
    assert entry.stream_metrics.stream_state == StreamLifecycleState.STREAM_CANCELLED.value

    export = stack.metrics_export()
    assert metric_value(export, f"{PROMETHEUS_PREFIX}_streams_cancelled_total") >= 1.0
    await stack.shutdown()


async def scenario_backend_stream_failure() -> None:
    backend = MockInferenceBackend()
    backend.enable_stream_failure(True)
    stack = _stack_with_stream_events(backend)
    await stack.startup()
    submit = stream_submit()
    await stack.orchestrator.lifecycle.process_through_queued(submit)
    session = StreamSession.create(
        request_id=submit.inference_request.request_id,
        correlation_id=submit.request_context.trace_id,
        model=submit.inference_request.model,
    )
    engine = StreamEngine(stack.stack, stream_events=stack.stack.stream_events)

    events: list[str] = []
    async for sse in engine.stream_sse(session, submit):
        events.append(sse)

    assert session.state == StreamLifecycleState.STREAM_FAILED
    entry = stack.cp.lifecycle.get_entry(submit.inference_request.request_id)
    assert entry.state == RequestState.FAILED

    export = stack.metrics_export()
    assert metric_value(export, f"{PROMETHEUS_PREFIX}_streams_failed_total") >= 1.0
    await stack.shutdown()


async def scenario_client_disconnect() -> None:
    """Simulate disconnect via disconnect_check callback."""
    stack = _stack_with_stream_events()
    await stack.startup()
    submit = stream_submit()
    await stack.orchestrator.lifecycle.process_through_queued(submit)
    session = StreamSession.create(
        request_id=submit.inference_request.request_id,
        correlation_id=submit.request_context.trace_id,
        model=submit.inference_request.model,
    )
    engine = StreamEngine(stack.stack, stream_events=stack.stack.stream_events)
    token_seen = False

    async def disconnected() -> bool:
        nonlocal token_seen
        return token_seen

    async for sse in engine.stream_sse(session, submit, disconnect_check=disconnected):
        if "chat.completion.chunk" in sse and "content" in sse:
            token_seen = True

    entry = stack.cp.lifecycle.get_entry(submit.inference_request.request_id)
    assert entry.state == RequestState.CANCELLED
    assert entry.stream_metrics is not None
    await stack.shutdown()


async def main() -> None:
    await scenario_successful_streaming()
    await scenario_stream_cancellation()
    await scenario_backend_stream_failure()
    await scenario_client_disconnect()
    print("stream_validation: all scenarios passed")


if __name__ == "__main__":
    asyncio.run(main())
