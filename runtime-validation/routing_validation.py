#!/usr/bin/env python3
"""Session 20 routing validation. Run: python runtime-validation/routing_validation.py"""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

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
from control_plane.registry.model_registry import default_model_registry
from control_plane.routing.engine import RoutingEngine
from control_plane.routing.events import RoutingEventEmitter, RoutingEventType
from control_plane.routing.provider import AdapterBackendProvider
from gpu_inference_observability import StructuredLogger
from gpu_inference_observability.registry.registry import PROMETHEUS_PREFIX
from inference_adapter.config import Settings as AdapterSettings

from api_gateway.runtime.routing_setup import register_routing_backends
from harness import ValidationStack, metric_value, submit_request


def submit_for_model(model: str) -> SubmitRequest:
    rid = uuid4()
    return SubmitRequest(
        inference_request=InferenceRequest(
            request_id=rid,
            model=model,
            messages=[Message(role=MessageRole.USER, content="routing validation")],
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


class RoutingValidationStack(ValidationStack):
    def __init__(self) -> None:
        super().__init__(adapter_settings=AdapterSettings(register_mock_backend=False))
        register_routing_backends(self.adapter)
        self.routing_events = RoutingEventEmitter(
            StructuredLogger("routing"),
            trace_recorder=self.trace_recorder,
        )
        self.routing_engine = RoutingEngine(
            default_model_registry(),
            AdapterBackendProvider(self.adapter),
            events=self.routing_events,
            metrics_recorder=self.metrics_recorder,
        )
        from scheduler import ControlPlaneQueueReader, create_application as create_scheduler
        from scheduler.integrations.embedded_adapter import EmbeddedAdapterClient

        self.scheduler = create_scheduler(
            ControlPlaneQueueReader(self.cp.queue),
            adapter_client=EmbeddedAdapterClient(self.adapter),
            trace_recorder=self.trace_recorder,
            metrics_recorder=self.metrics_recorder,
            trace_manager=self.trace_manager,
            routing_engine=self.routing_engine,
        )
        self.stack.scheduler = self.scheduler
        from api_gateway.runtime.orchestrator import RequestPathOrchestrator

        self.orchestrator = RequestPathOrchestrator(self.stack)


def _routing_events(stack: RoutingValidationStack, request_id: UUID) -> set[str]:
    timeline = stack.trace_inspector.get_request_timeline(request_id)
    return {
        e.event_type
        for e in timeline.events
        if (e.extra or {}).get("routing_event")
    }


async def scenario_explicit_model_routing(stack: RoutingValidationStack) -> None:
    submit = submit_for_model("demo")
    entry = await stack.orchestrator.execute_full_path(submit)
    assert entry.state == RequestState.COMPLETED
    assert entry.backend_id == "mock"
    events = _routing_events(stack, submit.inference_request.request_id)
    assert RoutingEventType.ROUTING_COMPLETED.value in events
    assert RoutingEventType.BACKEND_SELECTED.value in events


async def scenario_latency_tier_routing(stack: RoutingValidationStack) -> None:
    submit = submit_for_model("demo-fast")
    entry = await stack.orchestrator.execute_full_path(submit)
    assert entry.state == RequestState.COMPLETED
    assert entry.backend_id == "mock-fast"


async def scenario_quality_tier_routing(stack: RoutingValidationStack) -> None:
    submit = submit_for_model("demo-quality")
    entry = await stack.orchestrator.execute_full_path(submit)
    assert entry.state == RequestState.COMPLETED
    assert entry.backend_id == "mock-quality"


async def scenario_backend_failure_fallback(stack: RoutingValidationStack) -> None:
    submit = submit_for_model("demo-fallback")
    entry = await stack.orchestrator.execute_full_path(submit)
    assert entry.state == RequestState.COMPLETED
    assert entry.backend_id == "mock"
    events = _routing_events(stack, submit.inference_request.request_id)
    assert RoutingEventType.FALLBACK_INVOKED.value in events


async def scenario_unavailable_model_routing(stack: RoutingValidationStack) -> None:
    submit = submit_for_model("missing-model")
    result = stack.routing_engine.route(
        request_id=submit.inference_request.request_id,
        model_id="missing-model",
    )
    assert not result.success
    assert result.error is not None
    events = _routing_events(stack, submit.inference_request.request_id)
    assert RoutingEventType.ROUTING_FAILED.value in events


async def main() -> None:
    stack = RoutingValidationStack()
    await stack.startup()
    await scenario_explicit_model_routing(stack)
    await scenario_latency_tier_routing(stack)
    await scenario_quality_tier_routing(stack)
    await scenario_backend_failure_fallback(stack)
    await scenario_unavailable_model_routing(stack)

    export = stack.metrics_export()
    assert metric_value(export, f"{PROMETHEUS_PREFIX}_routing_decisions_total") >= 4.0
    assert metric_value(export, f"{PROMETHEUS_PREFIX}_model_requests_total") >= 4.0
    assert metric_value(export, f"{PROMETHEUS_PREFIX}_backend_selection_total") >= 4.0
    assert metric_value(export, f"{PROMETHEUS_PREFIX}_fallback_invocations_total") >= 1.0
    assert metric_value(export, f"{PROMETHEUS_PREFIX}_routing_failures_total") >= 1.0

    await stack.shutdown()
    print("routing_validation: all scenarios passed")


if __name__ == "__main__":
    asyncio.run(main())
