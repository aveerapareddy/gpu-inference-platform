"""Embedded platform stack: control plane, scheduler, inference adapter."""

from __future__ import annotations

from dataclasses import dataclass

from control_plane.application import ControlPlaneApplication, create_application as create_cp
from gpu_inference_observability.registry.recorder import RuntimeMetricsRecorder
from gpu_inference_observability.registry.registry import MetricsRegistry
from gpu_inference_observability.runtime.inspection import TraceInspector
from gpu_inference_observability.runtime.recorder import RuntimeEventRecorder
from gpu_inference_observability.runtime.store import RequestTraceStore
from inference_adapter.application import InferenceAdapterApplication, create_application as create_adapter
from scheduler import ControlPlaneQueueReader, create_application as create_scheduler
from scheduler.integrations.embedded_adapter import EmbeddedAdapterClient


@dataclass
class PlatformStack:
    control_plane: ControlPlaneApplication
    scheduler: object
    adapter: InferenceAdapterApplication
    trace_store: RequestTraceStore | None = None
    trace_recorder: RuntimeEventRecorder | None = None
    trace_inspector: TraceInspector | None = None
    metrics_registry: MetricsRegistry | None = None
    metrics_recorder: RuntimeMetricsRecorder | None = None

    async def startup(self) -> None:
        await self.control_plane.startup()
        await self.adapter.startup()
        await self.scheduler.startup()

    async def shutdown(self) -> None:
        await self.scheduler.shutdown()
        await self.adapter.shutdown()
        await self.control_plane.shutdown()


def create_platform_stack() -> PlatformStack:
    trace_store = RequestTraceStore()
    trace_recorder = RuntimeEventRecorder(trace_store)
    trace_inspector = TraceInspector(trace_store)
    metrics_registry = MetricsRegistry()
    metrics_recorder = RuntimeMetricsRecorder(metrics_registry)
    cp = create_cp(trace_recorder=trace_recorder, metrics_recorder=metrics_recorder)
    adapter = create_adapter(trace_recorder=trace_recorder, metrics_recorder=metrics_recorder)
    scheduler = create_scheduler(
        ControlPlaneQueueReader(cp.queue),
        adapter_client=EmbeddedAdapterClient(adapter),
        trace_recorder=trace_recorder,
        metrics_recorder=metrics_recorder,
    )
    return PlatformStack(
        control_plane=cp,
        scheduler=scheduler,
        adapter=adapter,
        trace_store=trace_store,
        trace_recorder=trace_recorder,
        trace_inspector=trace_inspector,
        metrics_registry=metrics_registry,
        metrics_recorder=metrics_recorder,
    )
