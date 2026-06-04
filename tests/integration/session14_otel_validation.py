#!/usr/bin/env python3
"""Session 14 OpenTelemetry validation. Run: python tests/integration/session14_otel_validation.py"""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone
from uuid import uuid4

from common_schemas.inference_request import InferenceRequest, Message, RequestContext, SubmitRequest
from common_schemas.states import MessageRole, RequestState
from control_plane.admission.framework import AdmissionFramework
from control_plane.admission.interfaces import AdmissionEvaluator, AdmissionOutcome, AdmissionResult
from control_plane.config import Settings as CPSettings
from control_plane.registry.models import RegisteredRequest
from gpu_inference_observability.otel import SpanName, TraceSpanInspector
from gpu_inference_observability.otel.config import TraceExportConfig, TraceExporterType
from gpu_inference_observability.otel.manager import TraceManager
from inference_adapter.backends.mock import MockInferenceBackend
from inference_adapter.config import Settings as AdapterSettings

from api_gateway.runtime.integrated_client import IntegratedPlatformClient
from api_gateway.runtime.orchestrator import RequestPathOrchestrator
from api_gateway.runtime.stack import PlatformStack, create_platform_stack
from gpu_inference_observability.registry.recorder import RuntimeMetricsRecorder
from gpu_inference_observability.registry.registry import MetricsRegistry
from gpu_inference_observability.runtime.recorder import RuntimeEventRecorder
from gpu_inference_observability.runtime.store import RequestTraceStore
from control_plane import create_application as create_cp
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
            messages=[Message(role=MessageRole.USER, content="otel")],
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


class _RejectAdmission(AdmissionEvaluator):
    async def evaluate(self, entry: RegisteredRequest) -> AdmissionResult:
        return AdmissionResult(outcome=AdmissionOutcome.REJECT, reason="admission_policy_failed")


def _stack(
    *,
    cp=None,
    sched=None,
    adapter=None,
    trace_manager: TraceManager,
) -> PlatformStack:
    return PlatformStack(
        control_plane=cp,
        scheduler=sched,
        adapter=adapter,
        trace_manager=trace_manager,
    )


def _find_span_by_id(spans, span_id: int):
    for span in spans:
        if span.context.span_id == span_id:
            return span
    return None


def _is_descendant(spans, ancestor, descendant) -> bool:
    current = descendant
    while current is not None and current.parent is not None:
        if current.parent.span_id == ancestor.context.span_id:
            return True
        current = _find_span_by_id(spans, current.parent.span_id)
    return False


def _assert_success_hierarchy(inspector: TraceSpanInspector, submit: SubmitRequest) -> None:
    inspector.assert_single_trace()
    request_id = str(submit.inference_request.request_id)
    correlation_id = submit.request_context.trace_id
    spans = inspector.finished_spans()

    roots = inspector.spans_named(SpanName.REQUEST.value)
    assert roots, "missing request root span"
    root = roots[0]
    assert root.parent is None, "request span should be root"
    inspector.assert_request_attributes(root, request_id=request_id, correlation_id=correlation_id)

    required = [
        SpanName.VALIDATION.value,
        SpanName.ADMISSION.value,
        SpanName.QUEUE.value,
        SpanName.SCHEDULER.value,
        SpanName.BATCH.value,
        SpanName.BACKEND_SUBMISSION.value,
        SpanName.COMPLETION.value,
    ]
    for name in required:
        matches = inspector.spans_named(name)
        assert matches, f"missing span {name}"
        child = matches[0]
        inspector.assert_request_attributes(child, request_id=request_id, correlation_id=correlation_id)
        assert _is_descendant(spans, root, child), f"{name} not under request span"

    scheduler = inspector.spans_named(SpanName.SCHEDULER.value)[0]
    batch = inspector.spans_named(SpanName.BATCH.value)[0]
    assert _is_descendant(spans, scheduler, batch), "batch span should descend from scheduler span"


async def scenario_successful_trace() -> None:
    TraceManager.clear_collected_spans()
    stack = create_platform_stack()
    await stack.startup()
    submit = _submit()
    client = IntegratedPlatformClient(stack)
    await client.accept_request(submit)
    stack.trace_manager.force_flush()

    exporter = stack.trace_manager.memory_exporter
    assert exporter is not None
    inspector = TraceSpanInspector(exporter)
    _assert_success_hierarchy(inspector, submit)
    await stack.shutdown()


async def scenario_admission_rejection_trace() -> None:
    TraceManager.clear_collected_spans()
    trace_manager = TraceManager(TraceExportConfig(exporter=TraceExporterType.MEMORY))
    cp = create_cp(
        admission=AdmissionFramework(evaluators=[_RejectAdmission()]),
        trace_manager=trace_manager,
    )
    await cp.startup()
    adapter = create_adapter(trace_manager=trace_manager)
    await adapter.startup()
    sched = create_scheduler(
        ControlPlaneQueueReader(cp.queue),
        SchedSettings(tick_interval_ms=60000),
        adapter_client=EmbeddedAdapterClient(adapter),
        trace_manager=trace_manager,
    )
    await sched.startup()
    stack = _stack(cp=cp, sched=sched, adapter=adapter, trace_manager=trace_manager)
    submit = _submit()

    with trace_manager.span(
        SpanName.REQUEST,
        component="gateway",
        request_id=submit.inference_request.request_id,
        correlation_id=submit.request_context.trace_id,
    ):
        entry = await RequestPathOrchestrator(stack).execute_full_path(submit)

    assert entry.state == RequestState.REJECTED
    trace_manager.force_flush()
    inspector = TraceSpanInspector(trace_manager.memory_exporter)
    admission = inspector.spans_named(SpanName.ADMISSION.value)
    assert admission
    attrs = inspector.span_attributes(admission[0])
    assert attrs.get("failure_type") == "admission_rejected"
    await stack.shutdown()


async def scenario_scheduler_batch_rejection_trace() -> None:
    TraceManager.clear_collected_spans()
    trace_manager = TraceManager(TraceExportConfig(exporter=TraceExporterType.MEMORY))
    cp = create_cp(trace_manager=trace_manager)
    await cp.startup()
    adapter = create_adapter(trace_manager=trace_manager)
    await adapter.startup()
    sched = create_scheduler(
        ControlPlaneQueueReader(cp.queue),
        SchedSettings(max_candidate_requests=5, max_batch_size=1, tick_interval_ms=60000),
        adapter_client=EmbeddedAdapterClient(adapter),
        trace_manager=trace_manager,
    )
    await sched.startup()
    stack = _stack(cp=cp, sched=sched, adapter=adapter, trace_manager=trace_manager)
    orchestrator = RequestPathOrchestrator(stack)
    submit1 = _submit()
    submit2 = _submit()

    await cp.lifecycle.process_through_queued(submit1)
    await cp.lifecycle.process_through_queued(submit2)

    with trace_manager.span(
        SpanName.REQUEST,
        component="gateway",
        request_id=submit2.inference_request.request_id,
        correlation_id=submit2.request_context.trace_id,
    ):
        result = await sched.run_scheduling_cycle()
        entry = orchestrator._finalize_request(submit2.inference_request.request_id, result, submit2)

    assert entry.state == RequestState.FAILED
    trace_manager.force_flush()
    inspector = TraceSpanInspector(trace_manager.memory_exporter)
    batch_spans = [
        span
        for span in inspector.spans_named(SpanName.BATCH.value)
        if inspector.span_attributes(span).get("failure_type") == "batch_rejected"
    ]
    assert batch_spans
    assert inspector.span_attributes(batch_spans[0]).get("failure_type") == "batch_rejected"
    await stack.shutdown()


async def scenario_backend_rejection_trace() -> None:
    TraceManager.clear_collected_spans()
    trace_manager = TraceManager(TraceExportConfig(exporter=TraceExporterType.MEMORY))
    cp = create_cp(trace_manager=trace_manager)
    await cp.startup()
    adapter = create_adapter(AdapterSettings(register_mock_backend=False), trace_manager=trace_manager)
    adapter.register_backend(MockInferenceBackend(backend_id="mock", reject=True))
    await adapter.startup()
    sched = create_scheduler(
        ControlPlaneQueueReader(cp.queue),
        SchedSettings(max_candidate_requests=5, max_batch_size=4, tick_interval_ms=60000),
        adapter_client=EmbeddedAdapterClient(adapter),
        trace_manager=trace_manager,
    )
    await sched.startup()
    stack = _stack(cp=cp, sched=sched, adapter=adapter, trace_manager=trace_manager)
    submit = _submit()

    with trace_manager.span(
        SpanName.REQUEST,
        component="gateway",
        request_id=submit.inference_request.request_id,
        correlation_id=submit.request_context.trace_id,
    ):
        entry = await RequestPathOrchestrator(stack).execute_full_path(submit)

    assert entry.state == RequestState.FAILED
    trace_manager.force_flush()
    inspector = TraceSpanInspector(trace_manager.memory_exporter)
    backend_spans = inspector.spans_named(SpanName.BACKEND_SUBMISSION.value)
    assert backend_spans
    failure_types = {inspector.span_attributes(s).get("failure_type") for s in backend_spans}
    assert "backend_rejected" in failure_types or "rejected" in failure_types
    await stack.shutdown()


async def main() -> int:
    await scenario_successful_trace()
    await scenario_admission_rejection_trace()
    await scenario_scheduler_batch_rejection_trace()
    await scenario_backend_rejection_trace()
    print("session14 otel validation: ok")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
