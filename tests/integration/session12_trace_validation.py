#!/usr/bin/env python3
"""Session 12 trace propagation validation. Run: python tests/integration/session12_trace_validation.py"""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone
from uuid import uuid4

from common_schemas.inference_request import InferenceRequest, Message, RequestContext, SubmitRequest
from common_schemas.states import MessageRole, RequestState
from control_plane.config import Settings as CPSettings
from gpu_inference_observability.runtime.models import RuntimeComponent
from inference_adapter import create_application as create_adapter
from inference_adapter.backends.mock import MockInferenceBackend
from inference_adapter.config import Settings as AdapterSettings

from api_gateway.runtime.integrated_client import IntegratedPlatformClient
from api_gateway.runtime.orchestrator import RequestPathOrchestrator
from api_gateway.runtime.stack import PlatformStack, create_platform_stack
from gpu_inference_observability.runtime.inspection import TraceInspector
from gpu_inference_observability.runtime.recorder import RuntimeEventRecorder
from gpu_inference_observability.runtime.store import RequestTraceStore
from scheduler import ControlPlaneQueueReader, create_application as create_scheduler
from scheduler.config import Settings as SchedSettings
from scheduler.integrations.embedded_adapter import EmbeddedAdapterClient


def _submit(model: str = "demo") -> SubmitRequest:
    rid = uuid4()
    return SubmitRequest(
        inference_request=InferenceRequest(
            request_id=rid,
            model=model,
            messages=[Message(role=MessageRole.USER, content="trace")],
            stream=False,
            max_tokens=8,
        ),
        request_context=RequestContext(
            request_id=rid,
            trace_id=f"trace-{rid}",
            span_id="span",
            arrival_time=datetime.now(timezone.utc),
            model=model,
            stream=False,
            gateway_instance_id="validation",
        ),
    )


def _stack_with_recorder(cp, sched, adapter) -> PlatformStack:
    trace_store = RequestTraceStore()
    trace_recorder = RuntimeEventRecorder(trace_store)
    trace_inspector = TraceInspector(trace_store)
    return PlatformStack(
        control_plane=cp,
        scheduler=sched,
        adapter=adapter,
        trace_store=trace_store,
        trace_recorder=trace_recorder,
        trace_inspector=trace_inspector,
    )


async def scenario_successful_trace() -> None:
    stack = create_platform_stack()
    await stack.startup()
    submit = _submit()
    client = IntegratedPlatformClient(stack)
    await client.accept_request(submit)

    inspector = stack.trace_inspector
    assert inspector is not None
    request_id = submit.inference_request.request_id
    trace = inspector.get_request_trace(request_id)
    assert trace is not None
    assert trace.context.correlation_id == submit.request_context.trace_id
    assert trace.context.batch_id is not None
    assert trace.context.backend_id == "mock"

    timeline = inspector.get_request_timeline(request_id)
    assert timeline is not None
    components = {event.component for event in timeline.events}
    assert RuntimeComponent.GATEWAY in components
    assert RuntimeComponent.CONTROL_PLANE in components
    assert RuntimeComponent.SCHEDULER in components
    assert RuntimeComponent.ADAPTER in components

    for event in timeline.events:
        assert event.request_id == request_id
        assert event.correlation_id == submit.request_context.trace_id

    metrics = inspector.get_request_metrics(request_id)
    assert metrics is not None
    assert metrics.event_count > 0
    assert metrics.failure_count == 0
    assert metrics.e2e_ms is not None

    ts = trace.timestamps
    assert ts.request_received_at is not None
    assert ts.request_validated_at is not None
    assert ts.request_admitted_at is not None
    assert ts.request_queued_at is not None
    assert ts.request_scheduled_at is not None
    assert ts.request_batched_at is not None
    assert ts.request_submitted_at is not None
    assert ts.request_completed_at is not None

    assert inspector.get_request_failures(request_id) == []
    assert inspector.get_queue_metrics(request_id) is not None
    assert inspector.get_scheduler_metrics(request_id) is not None
    assert inspector.get_batch_metrics(request_id) is not None
    assert inspector.get_backend_metrics(request_id) is not None

    await stack.shutdown()


async def scenario_failure_trace() -> None:
    from control_plane import create_application as create_cp

    trace_store = RequestTraceStore()
    trace_recorder = RuntimeEventRecorder(trace_store)
    trace_inspector = TraceInspector(trace_store)

    cp = create_cp(CPSettings(max_queue_size=10), trace_recorder=trace_recorder)
    await cp.startup()
    adapter = create_adapter(
        AdapterSettings(register_mock_backend=False),
        trace_recorder=trace_recorder,
    )
    adapter.register_backend(MockInferenceBackend(backend_id="mock", reject=True))
    await adapter.startup()
    sched = create_scheduler(
        ControlPlaneQueueReader(cp.queue),
        SchedSettings(max_candidate_requests=5, max_batch_size=4, tick_interval_ms=60000),
        adapter_client=EmbeddedAdapterClient(adapter),
        trace_recorder=trace_recorder,
    )
    await sched.startup()
    stack = _stack_with_recorder(cp, sched, adapter)
    orchestrator = RequestPathOrchestrator(stack)

    submit = _submit()
    trace_recorder.record_gateway_receive(
        request_id=submit.inference_request.request_id,
        correlation_id=submit.request_context.trace_id,
    )
    entry = await orchestrator.execute_full_path(submit)
    assert entry.state == RequestState.FAILED

    failures = trace_inspector.get_request_failures(submit.inference_request.request_id)
    assert len(failures) >= 1
    assert failures[0].failure_reason

    await stack.shutdown()


async def main() -> int:
    await scenario_successful_trace()
    await scenario_failure_trace()
    print("session12 trace validation: ok")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
