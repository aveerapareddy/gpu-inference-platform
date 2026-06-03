#!/usr/bin/env python3
"""Session 13 metrics validation. Run: python tests/integration/session13_metrics_validation.py"""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone
from uuid import uuid4

from common_schemas.inference_request import InferenceRequest, Message, RequestContext, SubmitRequest
from common_schemas.states import MessageRole, RequestState
from control_plane.config import Settings as CPSettings
from gpu_inference_observability.registry.registry import PROMETHEUS_PREFIX
from inference_adapter.backends.mock import MockInferenceBackend
from inference_adapter.config import Settings as AdapterSettings

from api_gateway.runtime.integrated_client import IntegratedPlatformClient
from api_gateway.runtime.orchestrator import RequestPathOrchestrator
from api_gateway.runtime.stack import PlatformStack, create_platform_stack
from gpu_inference_observability.registry.recorder import RuntimeMetricsRecorder
from gpu_inference_observability.registry.registry import MetricsRegistry
from gpu_inference_observability.runtime.recorder import RuntimeEventRecorder
from gpu_inference_observability.runtime.store import RequestTraceStore
from inference_adapter import create_application as create_adapter
from scheduler import ControlPlaneQueueReader, create_application as create_scheduler
from scheduler.config import Settings as SchedSettings
from scheduler.integrations.embedded_adapter import EmbeddedAdapterClient


def _submit(model: str = "demo") -> SubmitRequest:
    rid = uuid4()
    return SubmitRequest(
        inference_request=InferenceRequest(
            request_id=rid,
            model=model,
            messages=[Message(role=MessageRole.USER, content="metrics")],
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


def _metric_value(export: str, name: str) -> float:
    total = 0.0
    for line in export.splitlines():
        if line.startswith("#"):
            continue
        if not line.startswith(name):
            continue
        total += float(line.split()[-1])
    return total


def _assert_metric_present(export: str, name: str) -> None:
    assert name in export, f"missing metric {name}"


async def scenario_success_metrics() -> None:
    stack = create_platform_stack()
    await stack.startup()
    client = IntegratedPlatformClient(stack)
    await client.accept_request(_submit())

    registry = stack.metrics_registry
    assert registry is not None
    export = registry.export_prometheus().decode()

    _assert_metric_present(export, f"{PROMETHEUS_PREFIX}_requests_received_total")
    _assert_metric_present(export, f"{PROMETHEUS_PREFIX}_requests_completed_total")
    _assert_metric_present(export, f"{PROMETHEUS_PREFIX}_queue_enqueue_total")
    _assert_metric_present(export, f"{PROMETHEUS_PREFIX}_scheduler_cycles_total")
    _assert_metric_present(export, f"{PROMETHEUS_PREFIX}_batches_created_total")
    _assert_metric_present(export, f"{PROMETHEUS_PREFIX}_backend_submissions_total")
    _assert_metric_present(export, f"{PROMETHEUS_PREFIX}_backend_acceptance_total")

    assert _metric_value(export, f"{PROMETHEUS_PREFIX}_requests_received_total") >= 1.0
    assert _metric_value(export, f"{PROMETHEUS_PREFIX}_requests_completed_total") >= 1.0
    assert _metric_value(export, f"{PROMETHEUS_PREFIX}_queue_enqueue_total") >= 1.0
    assert _metric_value(export, f"{PROMETHEUS_PREFIX}_scheduler_cycles_total") >= 1.0
    assert _metric_value(export, f"{PROMETHEUS_PREFIX}_batches_created_total") >= 1.0
    assert _metric_value(export, f"{PROMETHEUS_PREFIX}_backend_submissions_total") >= 1.0
    assert _metric_value(export, f"{PROMETHEUS_PREFIX}_backend_acceptance_total") >= 1.0

    await stack.shutdown()


async def scenario_backend_rejection_metrics() -> None:
    from control_plane import create_application as create_cp

    metrics_registry = MetricsRegistry()
    metrics_recorder = RuntimeMetricsRecorder(metrics_registry)
    trace_recorder = RuntimeEventRecorder(RequestTraceStore())

    cp = create_cp(CPSettings(max_queue_size=10), trace_recorder=trace_recorder, metrics_recorder=metrics_recorder)
    await cp.startup()
    adapter = create_adapter(
        AdapterSettings(register_mock_backend=False),
        trace_recorder=trace_recorder,
        metrics_recorder=metrics_recorder,
    )
    adapter.register_backend(MockInferenceBackend(backend_id="mock", reject=True))
    await adapter.startup()
    sched = create_scheduler(
        ControlPlaneQueueReader(cp.queue),
        SchedSettings(max_candidate_requests=5, max_batch_size=4, tick_interval_ms=60000),
        adapter_client=EmbeddedAdapterClient(adapter),
        trace_recorder=trace_recorder,
        metrics_recorder=metrics_recorder,
    )
    await sched.startup()
    stack = PlatformStack(
        control_plane=cp,
        scheduler=sched,
        adapter=adapter,
        metrics_registry=metrics_registry,
        metrics_recorder=metrics_recorder,
    )
    orchestrator = RequestPathOrchestrator(stack)

    entry = await orchestrator.execute_full_path(_submit())
    assert entry.state == RequestState.FAILED

    export = metrics_registry.export_prometheus().decode()
    assert _metric_value(export, f"{PROMETHEUS_PREFIX}_backend_rejections_total") >= 1.0
    assert _metric_value(export, f"{PROMETHEUS_PREFIX}_requests_failed_total") >= 1.0

    await stack.shutdown()


async def scenario_prometheus_endpoint() -> None:
    from api_gateway.app import create_app
    from httpx import ASGITransport, AsyncClient

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async with app.router.lifespan_context(app):
            response = await client.get("/metrics")
    assert response.status_code == 200
    assert "gpu_inference_requests_received_total" in response.text


async def main() -> int:
    await scenario_success_metrics()
    await scenario_backend_rejection_metrics()
    await scenario_prometheus_endpoint()
    print("session13 metrics validation: ok")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
