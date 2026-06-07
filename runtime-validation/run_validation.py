#!/usr/bin/env python3
"""Session 15 reliability validation harness. Run: python runtime-validation/run_validation.py"""

from __future__ import annotations

import asyncio
import sys
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

from common_schemas.states import FailureReason, RequestState
from control_plane.config import Settings as CPSettings
from control_plane.errors import InvalidTransitionError
from control_plane.lifecycle.transitions import is_allowed_transition
from gpu_inference_observability.failure_injection.config import FailureInjectionConfig, FailurePoint
from gpu_inference_observability.failure_injection.injector import FailureInjector
from gpu_inference_observability.otel import SpanName, TraceSpanInspector
from gpu_inference_observability.registry.registry import PROMETHEUS_PREFIX
from inference_adapter.backend.state import BackendState
from inference_adapter.config import Settings as AdapterSettings

from api_gateway.runtime.integrated_client import IntegratedPlatformClient
from harness import (
    InjectableMockBackend,
    ValidationStack,
    corrupt_queue_without_lifecycle,
    force_queue_timeout,
    metric_value,
    submit_request,
)
from scheduler.config import Settings as SchedSettings


async def scenario_success_path() -> None:
    injector = FailureInjector()
    stack = ValidationStack(backend=InjectableMockBackend(injector))
    await stack.startup()
    entry = await stack.orchestrator.execute_full_path(submit_request())
    assert entry.state == RequestState.COMPLETED
    export = stack.metrics_export()
    assert metric_value(export, f"{PROMETHEUS_PREFIX}_requests_completed_total") >= 1.0
    await stack.shutdown()


async def scenario_queue_full() -> None:
    injector = FailureInjector()
    stack = ValidationStack(
        cp_settings=CPSettings(max_queue_size=1, queue_timeout_ms=60_000),
        backend=InjectableMockBackend(injector),
    )
    await stack.startup()
    first = await stack.orchestrator.execute_full_path(submit_request())
    assert first.state == RequestState.COMPLETED
    second = await stack.orchestrator.lifecycle.process_through_queued(submit_request())
    assert second.state == RequestState.REJECTED
    assert second.failure_reason == FailureReason.QUEUE_FULL
    export = stack.metrics_export()
    assert metric_value(export, f"{PROMETHEUS_PREFIX}_requests_rejected_total") >= 1.0
    failures = stack.trace_failures(second.request_id)
    assert failures, "expected queue failure in trace store"
    await stack.shutdown()


async def scenario_queue_timeout() -> None:
    stack = ValidationStack(
        cp_settings=CPSettings(max_queue_size=10, queue_timeout_ms=100),
        backend=InjectableMockBackend(FailureInjector()),
    )
    await stack.startup()
    submit = submit_request()
    entry = await stack.orchestrator.lifecycle.process_through_queued(submit)
    assert entry.state == RequestState.QUEUED
    queue_ops = stack.cp.queue._ops  # validation-only access
    assert force_queue_timeout(queue_ops, submit.inference_request.request_id)
    expired = stack.cp.queue.process_timeouts()
    assert expired
    timed_out = stack.cp.lifecycle.get_entry(submit.inference_request.request_id)
    assert timed_out.state == RequestState.TIMED_OUT
    export = stack.metrics_export()
    assert metric_value(export, f"{PROMETHEUS_PREFIX}_queue_timeout_total") >= 1.0
    assert metric_value(export, f"{PROMETHEUS_PREFIX}_requests_failed_total") >= 1.0
    failures = stack.trace_failures(submit.inference_request.request_id)
    assert any(f.failure_type == "queue_timeout" for f in failures)
    await stack.shutdown()


async def scenario_queue_corruption() -> None:
    stack = ValidationStack(backend=InjectableMockBackend(FailureInjector()))
    await stack.startup()
    submit = submit_request()
    entry = await stack.orchestrator.lifecycle.process_through_queued(submit)
    assert entry.state == RequestState.QUEUED
    queue_ops = stack.cp.queue._ops
    assert corrupt_queue_without_lifecycle(queue_ops, submit.inference_request.request_id)
    assert stack.cp.queue.depth() == 0
    assert stack.cp.lifecycle.get_entry(submit.inference_request.request_id).state == RequestState.QUEUED
    result = await stack.scheduler.run_scheduling_cycle()
    finalized = await stack.orchestrator._finalize_request(
        submit.inference_request.request_id,
        result,
        submit,
    )
    assert finalized.state == RequestState.FAILED
    export = stack.metrics_export()
    assert metric_value(export, f"{PROMETHEUS_PREFIX}_requests_failed_total") >= 1.0
    await stack.shutdown()


async def scenario_queue_invalid_removal() -> None:
    stack = ValidationStack(backend=InjectableMockBackend(FailureInjector()))
    await stack.startup()
    missing = stack.cp.queue.remove(uuid4())
    assert missing is None
    submit = submit_request()
    entry = await stack.orchestrator.lifecycle.process_through_queued(submit)
    removed = stack.cp.queue.remove(submit.inference_request.request_id)
    assert removed is not None
    assert stack.cp.lifecycle.get_entry(submit.inference_request.request_id).state == RequestState.QUEUED
    await stack.shutdown()


async def scenario_scheduler_crash() -> None:
    injector = FailureInjector(
        FailureInjectionConfig(enabled=True, point=FailurePoint.SCHEDULER_CRASH, message="injected crash"),
    )
    stack = ValidationStack(failure_injector=injector, backend=InjectableMockBackend(injector))
    await stack.startup()
    submit = submit_request()
    await stack.orchestrator.lifecycle.process_through_queued(submit)
    result = await stack.scheduler.run_scheduling_cycle()
    assert result.failure is not None
    export = stack.metrics_export()
    assert metric_value(export, f"{PROMETHEUS_PREFIX}_scheduler_failures_total") >= 1.0
    await stack.shutdown()


async def scenario_scheduler_timeout() -> None:
    injector = FailureInjector(
        FailureInjectionConfig(enabled=True, point=FailurePoint.SCHEDULER_TIMEOUT, message="injected timeout"),
    )
    stack = ValidationStack(failure_injector=injector, backend=InjectableMockBackend(injector))
    await stack.startup()
    await stack.orchestrator.lifecycle.process_through_queued(submit_request())
    result = await stack.scheduler.run_scheduling_cycle()
    assert result.failure is not None
    assert result.failure.reason == "scheduler_cycle_error"
    export = stack.metrics_export()
    assert metric_value(export, f"{PROMETHEUS_PREFIX}_scheduler_failures_total") >= 1.0
    await stack.shutdown()


async def scenario_scheduler_invalid_decision() -> None:
    stack = ValidationStack(backend=InjectableMockBackend(FailureInjector()))
    await stack.startup()
    submit = submit_request()
    await stack.orchestrator.lifecycle.process_through_queued(submit)
    phantom_id = uuid4()
    runner = stack.scheduler.cycle_runner
    original = runner._selector.evaluate

    def _inject_phantom(candidates, *, max_candidate_requests):
        decisions, selected, skipped = original(candidates, max_candidate_requests=max_candidate_requests)
        if candidates:
            selected = list(selected) + [phantom_id]
        return decisions, selected, skipped

    runner._selector.evaluate = _inject_phantom
    result = await stack.scheduler.run_scheduling_cycle()
    assert any(r.request_id == phantom_id for r in result.rejection_decisions)
    finalized = await stack.orchestrator._finalize_request(submit.inference_request.request_id, result, submit)
    assert finalized.state == RequestState.COMPLETED
    await stack.shutdown()


async def scenario_scheduler_invalid_batch_assignment() -> None:
    injector = FailureInjector(
        FailureInjectionConfig(
            enabled=True,
            point=FailurePoint.SCHEDULER_INVALID_BATCH_ASSIGNMENT,
        ),
    )
    stack = ValidationStack(failure_injector=injector, backend=InjectableMockBackend(injector))
    await stack.startup()
    submit = submit_request()
    await stack.orchestrator.lifecycle.process_through_queued(submit)
    result = await stack.scheduler.run_scheduling_cycle()
    assert result.rejection_decisions
    finalized = await stack.orchestrator._finalize_request(submit.inference_request.request_id, result, submit)
    assert finalized.state == RequestState.FAILED
    export = stack.metrics_export()
    assert metric_value(export, f"{PROMETHEUS_PREFIX}_requests_failed_total") >= 1.0
    await stack.shutdown()


async def scenario_batch_creation_failure() -> None:
    injector = FailureInjector(
        FailureInjectionConfig(enabled=True, point=FailurePoint.BATCH_CREATION_FAILURE),
    )
    stack = ValidationStack(failure_injector=injector, backend=InjectableMockBackend(injector))
    await stack.startup()
    submit = submit_request()
    await stack.orchestrator.lifecycle.process_through_queued(submit)
    result = await stack.scheduler.run_scheduling_cycle()
    assert result.failure is not None or result.rejection_decisions
    await stack.shutdown()


async def scenario_batch_admission_failure() -> None:
    injector = FailureInjector(
        FailureInjectionConfig(enabled=True, point=FailurePoint.BATCH_ADMISSION_FAILURE),
    )
    stack = ValidationStack(failure_injector=injector, backend=InjectableMockBackend(injector))
    await stack.startup()
    submit = submit_request()
    await stack.orchestrator.lifecycle.process_through_queued(submit)
    result = await stack.scheduler.run_scheduling_cycle()
    assert result.rejection_decisions
    finalized = await stack.orchestrator._finalize_request(submit.inference_request.request_id, result, submit)
    assert finalized.state == RequestState.FAILED
    await stack.shutdown()


async def scenario_batch_cancellation() -> None:
    stack = ValidationStack(backend=InjectableMockBackend(FailureInjector()))
    await stack.startup()
    submit = submit_request()
    await stack.orchestrator.lifecycle.process_through_queued(submit)
    result = await stack.scheduler.run_scheduling_cycle()
    placement = next(p for p in result.placement_decisions if p.request_id == submit.inference_request.request_id)
    stack.orchestrator.lifecycle.transition(
        submit.inference_request.request_id,
        RequestState.SCHEDULED,
        batch_id=placement.batch_id,
    )
    stack.orchestrator.lifecycle.transition(submit.inference_request.request_id, RequestState.BATCHED)
    batch_result = stack.scheduler.batch.fail_request(submit.inference_request.request_id, reason="injected_cancel")
    assert batch_result.success
    export = stack.metrics_export()
    assert metric_value(export, f"{PROMETHEUS_PREFIX}_batch_failures_total") >= 1.0
    await stack.shutdown()


async def scenario_batch_corruption() -> None:
    stack = ValidationStack(backend=InjectableMockBackend(FailureInjector()))
    await stack.startup()
    submit = submit_request()
    await stack.orchestrator.lifecycle.process_through_queued(submit)
    result = await stack.scheduler.run_scheduling_cycle()
    placement = next(p for p in result.placement_decisions if p.request_id == submit.inference_request.request_id)
    engine = stack.scheduler.batch._engine
    engine._request_to_batch.pop(submit.inference_request.request_id, None)
    retire = engine.complete_request(submit.inference_request.request_id)
    assert not retire.success
    await stack.shutdown()


async def scenario_backend_unavailable() -> None:
    injector = FailureInjector()
    stack = ValidationStack(
        adapter_settings=AdapterSettings(register_mock_backend=False),
        backend=InjectableMockBackend(injector),
    )
    await stack.startup()
    stack.adapter.registry.set_state("mock", BackendState.UNHEALTHY)
    submit = submit_request()
    entry = await stack.orchestrator.execute_full_path(submit)
    assert entry.state == RequestState.FAILED
    export = stack.metrics_export()
    assert metric_value(export, f"{PROMETHEUS_PREFIX}_requests_failed_total") >= 1.0
    await stack.shutdown()


async def scenario_backend_timeout() -> None:
    injector = FailureInjector(
        FailureInjectionConfig(enabled=True, point=FailurePoint.BACKEND_TIMEOUT),
    )
    stack = ValidationStack(
        adapter_settings=AdapterSettings(register_mock_backend=False),
        failure_injector=injector,
        backend=InjectableMockBackend(injector),
    )
    await stack.startup()
    entry = await stack.orchestrator.execute_full_path(submit_request())
    assert entry.state == RequestState.FAILED
    export = stack.metrics_export()
    assert metric_value(export, f"{PROMETHEUS_PREFIX}_backend_failures_total") >= 1.0
    assert metric_value(export, f"{PROMETHEUS_PREFIX}_requests_failed_total") >= 1.0
    await stack.shutdown()


async def scenario_backend_rejection() -> None:
    injector = FailureInjector(
        FailureInjectionConfig(enabled=True, point=FailurePoint.BACKEND_REJECTION),
    )
    stack = ValidationStack(
        adapter_settings=AdapterSettings(register_mock_backend=False),
        backend=InjectableMockBackend(injector),
    )
    await stack.startup()
    entry = await stack.orchestrator.execute_full_path(submit_request())
    assert entry.state == RequestState.FAILED
    export = stack.metrics_export()
    assert metric_value(export, f"{PROMETHEUS_PREFIX}_backend_rejections_total") >= 1.0
    assert metric_value(export, f"{PROMETHEUS_PREFIX}_requests_failed_total") >= 1.0
    await stack.shutdown()


async def scenario_backend_internal_error() -> None:
    injector = FailureInjector(
        FailureInjectionConfig(enabled=True, point=FailurePoint.BACKEND_INTERNAL_ERROR),
    )
    stack = ValidationStack(
        adapter_settings=AdapterSettings(register_mock_backend=False),
        backend=InjectableMockBackend(injector),
    )
    await stack.startup()
    submit = submit_request()
    entry = await stack.orchestrator.execute_full_path(submit)
    assert entry.state == RequestState.FAILED
    export = stack.metrics_export()
    assert metric_value(export, f"{PROMETHEUS_PREFIX}_backend_failures_total") >= 1.0
    assert metric_value(export, f"{PROMETHEUS_PREFIX}_requests_failed_total") >= 1.0
    stack.trace_manager.force_flush()
    inspector = TraceSpanInspector(stack.trace_manager.memory_exporter)
    backend_spans = inspector.spans_named(SpanName.BACKEND_SUBMISSION.value)
    assert backend_spans
    await stack.shutdown()


def scenario_lifecycle_violations() -> None:
    assert not is_allowed_transition(RequestState.COMPLETED, RequestState.QUEUED)
    assert not is_allowed_transition(RequestState.FAILED, RequestState.ADMITTED)
    assert not is_allowed_transition(RequestState.REJECTED, RequestState.SCHEDULED)

    from control_plane import create_application as create_cp

    cp = create_cp()
    submit = submit_request()
    entry = cp.lifecycle.register(submit, initial_state=RequestState.RECEIVED)
    cp.lifecycle.transition(entry.request_id, RequestState.VALIDATED)
    cp.lifecycle.transition(entry.request_id, RequestState.ADMITTED)
    cp.lifecycle.transition(entry.request_id, RequestState.QUEUED)
    cp.lifecycle.transition(entry.request_id, RequestState.SCHEDULED)
    cp.lifecycle.transition(entry.request_id, RequestState.BATCHED)
    cp.lifecycle.transition(entry.request_id, RequestState.SUBMITTED)
    cp.lifecycle.complete_request(entry.request_id)

    for target in (RequestState.QUEUED, RequestState.ADMITTED, RequestState.SCHEDULED):
        try:
            cp.lifecycle.transition(entry.request_id, target)
            raise AssertionError(f"expected InvalidTransitionError for COMPLETED -> {target}")
        except InvalidTransitionError:
            pass

    failed = cp.lifecycle.mark_failed(entry.request_id, FailureReason.INTERNAL_ERROR, "already terminal")
    assert failed.state == RequestState.FAILED


SCENARIOS = [
    ("success_path", scenario_success_path),
    ("queue_full", scenario_queue_full),
    ("queue_timeout", scenario_queue_timeout),
    ("queue_corruption", scenario_queue_corruption),
    ("queue_invalid_removal", scenario_queue_invalid_removal),
    ("scheduler_crash", scenario_scheduler_crash),
    ("scheduler_timeout", scenario_scheduler_timeout),
    ("scheduler_invalid_decision", scenario_scheduler_invalid_decision),
    ("scheduler_invalid_batch_assignment", scenario_scheduler_invalid_batch_assignment),
    ("batch_creation_failure", scenario_batch_creation_failure),
    ("batch_admission_failure", scenario_batch_admission_failure),
    ("batch_cancellation", scenario_batch_cancellation),
    ("batch_corruption", scenario_batch_corruption),
    ("backend_unavailable", scenario_backend_unavailable),
    ("backend_timeout", scenario_backend_timeout),
    ("backend_rejection", scenario_backend_rejection),
    ("backend_internal_error", scenario_backend_internal_error),
    ("lifecycle_violations", scenario_lifecycle_violations),
]


async def main() -> int:
    for name, scenario in SCENARIOS:
        if asyncio.iscoroutinefunction(scenario):
            await scenario()
        else:
            scenario()
        print(f"  ok: {name}")
    print("runtime-validation: ok")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
