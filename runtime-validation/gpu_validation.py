#!/usr/bin/env python3
"""Session 21 GPU observability validation. Run: python runtime-validation/gpu_validation.py"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path

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

from gpu_inference_observability import StructuredLogger
from gpu_inference_observability.gpu.collector import GPUMetricsCollector, GPUCollectorConfig
from gpu_inference_observability.gpu.events import CapacityEventEmitter, CapacityEventType
from gpu_inference_observability.gpu.probes import SimulatedGPUProbe
from gpu_inference_observability.failure_injection.injector import FailureInjector
from gpu_inference_observability.registry.registry import PROMETHEUS_PREFIX

from harness import InjectableMockBackend, ValidationStack, metric_value, submit_request


@dataclass
class StaticRuntimeContext:
    requests: int
    sequences: int
    batches: int
    max_sequences: int = 32
    max_batch_slot_limit: int = 8

    def active_requests(self) -> int:
        return self.requests

    def active_sequences(self) -> int:
        return self.sequences

    def active_batches(self) -> int:
        return self.batches

    def max_concurrent_sequences(self) -> int:
        return self.max_sequences

    def max_batch_slots(self) -> int:
        return self.max_batch_slot_limit


def _capacity_events(trace_inspector) -> set[str]:
    from uuid import UUID

    rid = UUID("00000000-0000-4000-8000-000000000021")
    timeline = trace_inspector.get_request_timeline(rid)
    if timeline is None:
        return set()
    return {e.event_type for e in timeline.events if (e.extra or {}).get("capacity_event")}


def _build_collector(
    stack: ValidationStack,
    probe: SimulatedGPUProbe,
    context: StaticRuntimeContext,
) -> GPUMetricsCollector:
    events = CapacityEventEmitter(StructuredLogger("gpu_observability"), trace_recorder=stack.trace_recorder)
    return GPUMetricsCollector(
        metrics_recorder=stack.metrics_recorder,
        context_provider=context,
        events=events,
        probe=probe,
        config=GPUCollectorConfig(
            kv_cache_pressure_ratio=0.7,
            gpu_memory_threshold_ratio=0.8,
            capacity_warning_remaining=2,
        ),
    )


async def scenario_idle_system(stack: ValidationStack) -> None:
    probe = SimulatedGPUProbe()
    probe.set_state(utilization_percent=0.0, memory_used_bytes=0)
    collector = _build_collector(stack, probe, StaticRuntimeContext(0, 0, 0))
    snapshot = collector.collect()
    assert snapshot.devices[0].utilization_percent == 0.0
    export = stack.metrics_export()
    assert metric_value(export, f"{PROMETHEUS_PREFIX}_gpu_utilization_percent") == 0.0
    assert metric_value(export, f"{PROMETHEUS_PREFIX}_capacity_remaining") >= 8.0


async def scenario_moderate_load(stack: ValidationStack) -> None:
    probe = SimulatedGPUProbe()
    probe.set_state(utilization_percent=45.0, memory_used_bytes=6 * 1024 * 1024 * 1024)
    collector = _build_collector(stack, probe, StaticRuntimeContext(2, 4, 1))
    snapshot = collector.collect()
    assert snapshot.kv_cache.active_sequences == 4
    assert snapshot.memory.kv_cache_bytes > 0
    export = stack.metrics_export()
    assert metric_value(export, f"{PROMETHEUS_PREFIX}_active_sequences") == 4.0
    assert metric_value(export, f"{PROMETHEUS_PREFIX}_kv_cache_estimated_bytes") > 0.0


async def scenario_increasing_concurrency(stack: ValidationStack) -> None:
    probe = SimulatedGPUProbe()
    probe.set_state(utilization_percent=70.0, memory_used_bytes=10 * 1024 * 1024 * 1024)
    collector = _build_collector(stack, probe, StaticRuntimeContext(6, 12, 2, max_sequences=16))
    snapshot = collector.collect()
    assert snapshot.capacity.active_sequences == 12
    assert snapshot.capacity.capacity_remaining == 4


async def scenario_cache_pressure(stack: ValidationStack) -> None:
    probe = SimulatedGPUProbe()
    probe.set_state(utilization_percent=60.0, memory_used_bytes=12 * 1024 * 1024 * 1024)
    collector = _build_collector(stack, probe, StaticRuntimeContext(8, 14, 2, max_sequences=16))
    snapshot = collector.collect()
    assert snapshot.kv_cache.cache_occupancy_ratio >= 0.7
    events = _capacity_events(stack.trace_inspector)
    assert CapacityEventType.KV_CACHE_PRESSURE_DETECTED.value in events


async def scenario_capacity_exhaustion(stack: ValidationStack) -> None:
    probe = SimulatedGPUProbe()
    probe.set_state(utilization_percent=95.0, memory_used_bytes=15 * 1024 * 1024 * 1024)
    collector = _build_collector(
        stack,
        probe,
        StaticRuntimeContext(8, 16, 8, max_sequences=16, max_batch_slot_limit=8),
    )
    snapshot = collector.collect()
    assert snapshot.capacity.capacity_remaining == 0
    events = _capacity_events(stack.trace_inspector)
    assert CapacityEventType.CAPACITY_EXHAUSTED.value in events
    assert CapacityEventType.MEMORY_THRESHOLD_CROSSED.value in events


async def scenario_runtime_path_updates_metrics(stack: ValidationStack) -> None:
    await stack.startup()
    submit = submit_request()
    entry = await stack.orchestrator.execute_full_path(submit)
    assert entry.state.value == "completed"
    probe = SimulatedGPUProbe()
    probe.set_state(utilization_percent=10.0, memory_used_bytes=1024 * 1024)
    collector = _build_collector(
        stack,
        probe,
        StaticRuntimeContext(requests=0, sequences=0, batches=0),
    )
    collector.collect()
    export = stack.metrics_export()
    assert metric_value(export, f"{PROMETHEUS_PREFIX}_gpu_memory_used_bytes") > 0.0
    await stack.shutdown()


async def main() -> None:
    stack = ValidationStack(backend=InjectableMockBackend(FailureInjector()))
    await scenario_idle_system(stack)
    await scenario_moderate_load(stack)
    await scenario_increasing_concurrency(stack)
    await scenario_cache_pressure(stack)
    await scenario_capacity_exhaustion(stack)
    await scenario_runtime_path_updates_metrics(stack)
    print("gpu_validation: all scenarios passed")


if __name__ == "__main__":
    asyncio.run(main())
