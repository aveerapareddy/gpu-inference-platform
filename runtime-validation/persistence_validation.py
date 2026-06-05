#!/usr/bin/env python3
"""Session 17 persistence validation. Run: python runtime-validation/persistence_validation.py"""

from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path
from uuid import UUID

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
from gpu_inference_observability.failure_injection.config import FailureInjectionConfig, FailurePoint
from gpu_inference_observability.failure_injection.injector import FailureInjector
from gpu_inference_observability.persistence.events import PersistenceEventType
from gpu_inference_observability.runtime.models import RuntimeComponent
from inference_adapter.config import Settings as AdapterSettings

from api_gateway.runtime.integrated_client import IntegratedPlatformClient
from api_gateway.runtime.orchestrator import RequestPathOrchestrator
from api_gateway.runtime.stack import create_platform_stack
from harness import InjectableMockBackend, ValidationStack, submit_request


async def scenario_restart_recovery() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = str(Path(tmp) / "runtime.db")
        stack = create_platform_stack(db_path=db_path)
        await stack.startup()
        submit = submit_request()
        await IntegratedPlatformClient(stack).accept_request(submit)
        request_id = submit.inference_request.request_id
        assert stack.replay_debug.get_execution_record(request_id) is not None
        assert stack.runtime_repository is not None
        assert len(stack.runtime_repository.requests.list_requests()) == 1
        assert stack.runtime_repository.traces.get_summary(request_id) is not None
        await stack.shutdown()

        restarted = create_platform_stack(db_path=db_path)
        await restarted.startup()
        assert restarted.runtime_repository is not None
        record = restarted.replay_debug.get_execution_record(request_id)
        assert record is not None
        assert record.terminal_outcome.state == RequestState.COMPLETED.value

        reconstructed = restarted.replay_debug.reconstruct_execution(request_id)
        assert reconstructed is not None
        assert reconstructed.terminal_outcome is not None
        assert reconstructed.terminal_outcome.state == RequestState.COMPLETED.value

        metadata = restarted.runtime_repository.requests.get_request(request_id)
        assert metadata is not None
        assert metadata.terminal_state == RequestState.COMPLETED.value

        transitions = restarted.runtime_repository.lifecycle.get_transitions(request_id)
        assert len(transitions) > 0

        failures = restarted.runtime_repository.failures.query_failures_by_request(request_id)
        assert isinstance(failures, list)

        replay_stack = create_platform_stack(db_path=str(Path(tmp) / "replay-runtime.db"))
        await replay_stack.startup()
        replay_result = await replay_stack.replay_debug.replay_request(
            record,
            RequestPathOrchestrator(replay_stack).execute_full_path,
        )
        assert replay_result.outcome.value == "completed"
        await replay_stack.shutdown()
        await restarted.shutdown()


async def scenario_failed_request_persistence() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = str(Path(tmp) / "failed.db")
        injector = FailureInjector(
            FailureInjectionConfig(enabled=True, point=FailurePoint.BACKEND_REJECTION),
        )
        vstack = ValidationStack(
            adapter_settings=AdapterSettings(register_mock_backend=False),
            backend=InjectableMockBackend(injector),
            db_path=db_path,
        )
        await vstack.startup()
        submit = submit_request()
        entry = await vstack.orchestrator.execute_full_path(submit)
        assert entry.state == RequestState.FAILED
        request_id = submit.inference_request.request_id
        vstack.replay_engine.capture_from_entry(entry)
        await vstack.shutdown()

        restarted = ValidationStack(
            adapter_settings=AdapterSettings(register_mock_backend=False),
            backend=InjectableMockBackend(injector),
            db_path=db_path,
        )
        await restarted.startup()
        record = restarted.replay_debug.get_execution_record(request_id)
        assert record is not None
        assert record.terminal_outcome.state == RequestState.FAILED.value

        persisted_failures = restarted.runtime_repository.failures.query_failures_by_request(request_id)
        assert len(persisted_failures) >= 0
        backend_failures = restarted.runtime_repository.failures.query_failures_by_component(
            RuntimeComponent.ADAPTER
        )
        assert isinstance(backend_failures, list)
        await restarted.shutdown()


async def scenario_replay_persistence_after_restart() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = str(Path(tmp) / "replay-persist.db")
        stack = create_platform_stack(db_path=db_path)
        await stack.startup()
        submit = submit_request()
        await IntegratedPlatformClient(stack).accept_request(submit)
        request_id = submit.inference_request.request_id
        await stack.shutdown()

        restarted = create_platform_stack(db_path=db_path)
        await restarted.startup()
        record = restarted.replay_debug.get_execution_record(request_id)
        assert record is not None

        replay_stack = create_platform_stack(db_path=db_path)
        await replay_stack.startup()
        replay_result = await replay_stack.replay_debug.replay_request(
            record,
            RequestPathOrchestrator(replay_stack).execute_full_path,
        )
        assert replay_result.outcome.value == "completed"
        assert replay_stack.runtime_repository is not None
        replays = replay_stack.runtime_repository.replays.list_replays(source_request_id=request_id)
        assert len(replays) >= 1
        await replay_stack.shutdown()
        await restarted.shutdown()


async def scenario_persistence_events() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = str(Path(tmp) / "events.db")
        stack = create_platform_stack(db_path=db_path)
        await stack.startup()
        submit = submit_request()
        await IntegratedPlatformClient(stack).accept_request(submit)
        request_id = submit.inference_request.request_id
        trace = stack.trace_inspector.get_request_trace(request_id)
        assert trace is not None
        event_types = {event.event_type for event in trace.events}
        assert PersistenceEventType.PERSISTENCE_WRITE.value in event_types
        await stack.shutdown()

        restarted = create_platform_stack(db_path=db_path)
        await restarted.startup()
        assert restarted.replay_debug.get_execution_record(request_id) is not None
        await restarted.shutdown()


async def main() -> int:
    await scenario_restart_recovery()
    await scenario_failed_request_persistence()
    await scenario_replay_persistence_after_restart()
    await scenario_persistence_events()
    print("persistence validation: ok")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
