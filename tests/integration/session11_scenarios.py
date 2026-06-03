#!/usr/bin/env python3
"""Session 11 integration validation scenarios. Run: python tests/integration/session11_scenarios.py"""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone
from uuid import uuid4

from common_schemas.inference_request import InferenceRequest, Message, RequestContext, SubmitRequest
from common_schemas.states import FailureReason, MessageRole, RequestState
from control_plane.config import Settings as CPSettings
from control_plane.errors import InvalidTransitionError
from control_plane.lifecycle.transitions import is_allowed_transition
from inference_adapter import create_application as create_adapter
from inference_adapter.backends.mock import MockInferenceBackend
from inference_adapter.config import Settings as AdapterSettings

from api_gateway.runtime.integrated_client import IntegratedPlatformClient
from api_gateway.runtime.orchestrator import RequestPathOrchestrator
from api_gateway.runtime.stack import PlatformStack, create_platform_stack
from scheduler import ControlPlaneQueueReader, create_application as create_scheduler
from scheduler.config import Settings as SchedSettings
from scheduler.integrations.embedded_adapter import EmbeddedAdapterClient


def _submit(model: str = "demo") -> SubmitRequest:
    rid = uuid4()
    return SubmitRequest(
        inference_request=InferenceRequest(
            request_id=rid,
            model=model,
            messages=[Message(role=MessageRole.USER, content="validate")],
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


async def scenario_successful_request() -> None:
    stack = create_platform_stack()
    await stack.startup()
    client = IntegratedPlatformClient(stack)
    submit = _submit()
    result = await client.accept_request(submit)
    assert result.state == RequestState.COMPLETED
    assert result.entry.batch_id is not None
    assert result.entry.backend_id == "mock"
    assert result.entry.request_context.trace_id == submit.request_context.trace_id
    await stack.shutdown()


async def scenario_rejected_request() -> None:
    from control_plane import create_application as create_cp

    cp = create_cp(CPSettings(max_queue_size=1))
    await cp.startup()
    adapter = create_adapter()
    await adapter.startup()
    sched = create_scheduler(
        ControlPlaneQueueReader(cp.queue),
        SchedSettings(max_candidate_requests=5, max_batch_size=4, tick_interval_ms=60000),
        adapter_client=EmbeddedAdapterClient(adapter),
    )
    await sched.startup()
    stack = PlatformStack(control_plane=cp, scheduler=sched, adapter=adapter)
    orchestrator = RequestPathOrchestrator(stack)

    first = await orchestrator.execute_full_path(_submit())
    assert first.state == RequestState.COMPLETED

    second = await orchestrator.lifecycle.process_through_queued(_submit())
    assert second.state == RequestState.REJECTED

    await stack.shutdown()


async def scenario_backend_rejection() -> None:
    from control_plane import create_application as create_cp

    cp = create_cp(CPSettings(max_queue_size=10))
    await cp.startup()
    adapter = create_adapter(AdapterSettings(register_mock_backend=False))
    adapter.register_backend(MockInferenceBackend(backend_id="mock", reject=True))
    await adapter.startup()
    sched = create_scheduler(
        ControlPlaneQueueReader(cp.queue),
        SchedSettings(max_candidate_requests=5, max_batch_size=4, tick_interval_ms=60000),
        adapter_client=EmbeddedAdapterClient(adapter),
    )
    await sched.startup()
    stack = PlatformStack(control_plane=cp, scheduler=sched, adapter=adapter)
    orchestrator = RequestPathOrchestrator(stack)

    entry = await orchestrator.execute_full_path(_submit())
    assert entry.state == RequestState.FAILED
    assert entry.failure_reason == FailureReason.ADAPTER_ERROR

    await stack.shutdown()


def scenario_invalid_transition() -> None:
    assert not is_allowed_transition(RequestState.COMPLETED, RequestState.QUEUED)
    try:
        from control_plane import create_application as create_cp

        cp = create_cp()
        entry = cp.lifecycle.register(_submit(), initial_state=RequestState.RECEIVED)
        cp.lifecycle.transition(entry.request_id, RequestState.COMPLETED)
        raise AssertionError("expected InvalidTransitionError")
    except InvalidTransitionError:
        pass


async def scenario_scheduler_dispatch_failure() -> None:
    """Batch placed but adapter misconfigured (backend removed)."""
    from control_plane import create_application as create_cp

    cp = create_cp(CPSettings(max_queue_size=10))
    await cp.startup()
    adapter = create_adapter(AdapterSettings(register_mock_backend=False))
    await adapter.startup()
    sched = create_scheduler(
        ControlPlaneQueueReader(cp.queue),
        SchedSettings(max_candidate_requests=5, max_batch_size=4, tick_interval_ms=60000),
        adapter_client=EmbeddedAdapterClient(adapter),
    )
    await sched.startup()
    stack = PlatformStack(control_plane=cp, scheduler=sched, adapter=adapter)
    orchestrator = RequestPathOrchestrator(stack)

    entry = await orchestrator.execute_full_path(_submit())
    assert entry.state == RequestState.FAILED

    await stack.shutdown()


async def main() -> int:
    await scenario_successful_request()
    await scenario_rejected_request()
    await scenario_backend_rejection()
    scenario_invalid_transition()
    await scenario_scheduler_dispatch_failure()
    print("session11 scenarios: ok")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
