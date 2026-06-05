#!/usr/bin/env python3
"""Session 16 replay validation. Run: python runtime-validation/replay_validation.py"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for rel in (
    "packages/common-schemas/src",
    "packages/observability/src",
    "services/api-gateway/src",
    "services/control-plane/src",
    "services/scheduler/src",
    "services/inference-adapter/src",
    "runtime-validation",
):
    path = str(ROOT / rel)
    if path not in sys.path:
        sys.path.insert(0, path)

from common_schemas.states import RequestState
from control_plane.admission.framework import AdmissionFramework
from control_plane.admission.interfaces import AdmissionEvaluator, AdmissionOutcome, AdmissionResult
from control_plane.registry.models import RegisteredRequest
from gpu_inference_observability.failure_injection.config import FailureInjectionConfig, FailurePoint
from gpu_inference_observability.failure_injection.injector import FailureInjector
from gpu_inference_observability.runtime.replay.events import ReplayEventType
from inference_adapter.config import Settings as AdapterSettings

from api_gateway.runtime.integrated_client import IntegratedPlatformClient
from api_gateway.runtime.orchestrator import RequestPathOrchestrator
from api_gateway.runtime.stack import create_platform_stack
from harness import InjectableMockBackend, ValidationStack, submit_request


class _RejectAdmission(AdmissionEvaluator):
    async def evaluate(self, entry: RegisteredRequest) -> AdmissionResult:
        return AdmissionResult(outcome=AdmissionOutcome.REJECT, reason="admission_policy_failed")


async def scenario_successful_replay() -> None:
    stack = create_platform_stack()
    await stack.startup()
    submit = submit_request()
    await IntegratedPlatformClient(stack).accept_request(submit)

    original_id = submit.inference_request.request_id
    original_record = stack.replay_debug.get_execution_record(original_id)
    assert original_record is not None

    reconstructed = stack.replay_debug.reconstruct_execution(original_id)
    assert reconstructed is not None
    assert reconstructed.terminal_outcome.state == RequestState.COMPLETED.value

    replay_stack = create_platform_stack()
    await replay_stack.startup()
    replay_result = await replay_stack.replay_debug.replay_request(
        original_record,
        RequestPathOrchestrator(replay_stack).execute_full_path,
    )
    assert replay_result.outcome.value == "completed"

    comparison = replay_stack.replay_engine.compare(original_record, replay_result.execution_record)
    assert comparison.matches
    assert ReplayEventType.REPLAY_COMPLETED.value in replay_result.replay_events
    await stack.shutdown()
    await replay_stack.shutdown()


async def scenario_failed_replay() -> None:
    injector = FailureInjector(
        FailureInjectionConfig(enabled=True, point=FailurePoint.BACKEND_REJECTION),
    )
    vstack = ValidationStack(
        adapter_settings=AdapterSettings(register_mock_backend=False),
        backend=InjectableMockBackend(injector),
    )
    await vstack.startup()
    submit = submit_request()
    entry = await vstack.orchestrator.execute_full_path(submit)
    assert entry.state == RequestState.FAILED
    original_record = vstack.replay_engine.capture_from_entry(entry)
    assert original_record is not None

    replay_stack = ValidationStack(
        adapter_settings=AdapterSettings(register_mock_backend=False),
        backend=InjectableMockBackend(injector),
    )
    await replay_stack.startup()
    replay_result = await replay_stack.replay_debug.replay_request(
        original_record,
        replay_stack.orchestrator.execute_full_path,
    )
    assert replay_result.terminal_state == RequestState.FAILED.value

    comparison = replay_stack.replay_engine.compare(original_record, replay_result.execution_record)
    assert comparison.terminal_state_match
    await vstack.shutdown()
    await replay_stack.shutdown()


async def scenario_validation_rejection_replay() -> None:
    vstack = ValidationStack(
        admission=AdmissionFramework(evaluators=[_RejectAdmission()]),
        backend=InjectableMockBackend(FailureInjector()),
    )
    await vstack.startup()
    submit = submit_request()
    entry = await vstack.orchestrator.lifecycle.process_through_queued(submit)
    assert entry.state == RequestState.REJECTED
    original_record = vstack.replay_engine.capture_from_entry(entry)
    assert original_record.terminal_outcome.state == RequestState.REJECTED.value

    replay_stack = ValidationStack(
        admission=AdmissionFramework(evaluators=[_RejectAdmission()]),
        backend=InjectableMockBackend(FailureInjector()),
    )
    await replay_stack.startup()
    replay_result = await replay_stack.replay_debug.replay_request(
        original_record,
        replay_stack.orchestrator.lifecycle.process_through_queued,
    )
    assert replay_result.terminal_state == RequestState.REJECTED.value
    await vstack.shutdown()
    await replay_stack.shutdown()


async def scenario_scheduler_failure_replay() -> None:
    injector = FailureInjector(
        FailureInjectionConfig(enabled=True, point=FailurePoint.SCHEDULER_CRASH),
    )
    vstack = ValidationStack(
        failure_injector=injector,
        backend=InjectableMockBackend(injector),
    )
    await vstack.startup()
    submit = submit_request()
    await vstack.orchestrator.lifecycle.process_through_queued(submit)
    try:
        await vstack.orchestrator.execute_full_path(submit)
    except Exception:
        pass
    entry = vstack.cp.lifecycle.get_entry(submit.inference_request.request_id)
    original_record = vstack.replay_engine.capture_from_entry(entry)

    replay_stack = ValidationStack(
        failure_injector=FailureInjector(
            FailureInjectionConfig(enabled=True, point=FailurePoint.SCHEDULER_CRASH),
        ),
        backend=InjectableMockBackend(FailureInjector()),
    )
    await replay_stack.startup()
    replay_result = await replay_stack.replay_debug.replay_request(
        original_record,
        replay_stack.orchestrator.execute_full_path,
    )
    assert replay_result.outcome.value in {"failed", "error", "completed"}
    await vstack.shutdown()
    await replay_stack.shutdown()


async def scenario_backend_rejection_replay() -> None:
    injector = FailureInjector(
        FailureInjectionConfig(enabled=True, point=FailurePoint.BACKEND_REJECTION),
    )
    vstack = ValidationStack(
        adapter_settings=AdapterSettings(register_mock_backend=False),
        backend=InjectableMockBackend(injector),
    )
    await vstack.startup()
    submit = submit_request()
    entry = await vstack.orchestrator.execute_full_path(submit)
    original_record = vstack.replay_engine.capture_from_entry(entry)

    replay_stack = ValidationStack(
        adapter_settings=AdapterSettings(register_mock_backend=False),
        backend=InjectableMockBackend(injector),
    )
    await replay_stack.startup()
    replay_result = await replay_stack.replay_debug.replay_request(
        original_record,
        replay_stack.orchestrator.execute_full_path,
    )
    assert replay_result.terminal_state == RequestState.FAILED.value
    trace = replay_stack.trace_inspector.get_request_trace(replay_result.replay_request_id)
    assert trace is not None
    await vstack.shutdown()
    await replay_stack.shutdown()


async def scenario_execution_comparison() -> None:
    stack = create_platform_stack()
    await stack.startup()
    submit = submit_request()
    entry = await RequestPathOrchestrator(stack).execute_full_path(submit)
    original_record = stack.replay_engine.capture_from_entry(entry)

    reject_stack = ValidationStack(
        adapter_settings=AdapterSettings(register_mock_backend=False),
        backend=InjectableMockBackend(
            FailureInjector(FailureInjectionConfig(enabled=True, point=FailurePoint.BACKEND_REJECTION))
        ),
    )
    await reject_stack.startup()
    replay_result = await reject_stack.replay_debug.replay_request(
        original_record,
        reject_stack.orchestrator.execute_full_path,
    )
    comparison = reject_stack.replay_engine.compare(original_record, replay_result.execution_record)
    assert not comparison.matches
    assert len(comparison.differences) > 0
    await stack.shutdown()
    await reject_stack.shutdown()


async def main() -> int:
    await scenario_successful_replay()
    await scenario_failed_replay()
    await scenario_validation_rejection_replay()
    await scenario_scheduler_failure_replay()
    await scenario_backend_rejection_replay()
    await scenario_execution_comparison()
    print("replay validation: ok")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
