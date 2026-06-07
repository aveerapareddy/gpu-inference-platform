"""Embedded platform stack: control plane, scheduler, inference adapter."""

from __future__ import annotations

from dataclasses import dataclass

from control_plane.application import ControlPlaneApplication, create_application as create_cp
from gpu_inference_observability import StructuredLogger
from gpu_inference_observability.otel.config import TraceExportConfig, TraceExporterType
from gpu_inference_observability.otel.manager import TraceManager
from gpu_inference_observability.persistence.durable_store import DurableExecutionRecordStore
from gpu_inference_observability.persistence.events import PersistenceEventEmitter
from gpu_inference_observability.persistence.repository import RuntimeRepository
from gpu_inference_observability.persistence.sqlite.runtime_repository import SqliteRuntimeRepository
from gpu_inference_observability.registry.recorder import RuntimeMetricsRecorder
from gpu_inference_observability.registry.registry import MetricsRegistry
from gpu_inference_observability.runtime.inspection import TraceInspector
from gpu_inference_observability.runtime.recorder import RuntimeEventRecorder
from gpu_inference_observability.runtime.replay.debugging import ReplayDebugService
from gpu_inference_observability.runtime.replay.engine import ReplayEngine
from gpu_inference_observability.runtime.replay.events import ReplayEventEmitter
from gpu_inference_observability.runtime.replay.store import ExecutionRecordStore
from gpu_inference_observability.runtime.store import RequestTraceStore
from gpu_inference_observability.streaming.events import StreamEventEmitter
from inference_adapter.application import InferenceAdapterApplication, create_application as create_adapter
from scheduler import ControlPlaneQueueReader, create_application as create_scheduler
from scheduler.integrations.embedded_adapter import EmbeddedAdapterClient

from api_gateway.runtime.replay import submit_from_payload


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
    trace_manager: TraceManager | None = None
    execution_store: ExecutionRecordStore | None = None
    replay_engine: ReplayEngine | None = None
    replay_debug: ReplayDebugService | None = None
    runtime_repository: RuntimeRepository | None = None
    stream_events: StreamEventEmitter | None = None

    async def startup(self) -> None:
        await self.control_plane.startup()
        await self.adapter.startup()
        await self.scheduler.startup()

    async def shutdown(self) -> None:
        await self.scheduler.shutdown()
        await self.adapter.shutdown()
        await self.control_plane.shutdown()
        if self.trace_manager is not None:
            self.trace_manager.force_flush()
        if self.runtime_repository is not None:
            self.runtime_repository.close()


def create_platform_stack(
    *,
    trace_export: TraceExportConfig | None = None,
    db_path: str | None = None,
) -> PlatformStack:
    trace_store = RequestTraceStore()
    trace_recorder = RuntimeEventRecorder(trace_store)
    trace_inspector = TraceInspector(trace_store)
    runtime_repository: RuntimeRepository | None = None
    persistence_events: PersistenceEventEmitter | None = None

    if db_path is not None:
        persistence_events = PersistenceEventEmitter(
            StructuredLogger("persistence"),
            trace_recorder=trace_recorder,
        )
        runtime_repository = SqliteRuntimeRepository(db_path, events=persistence_events)
        execution_store: ExecutionRecordStore = DurableExecutionRecordStore(
            runtime_repository,
            events=persistence_events,
        )
        if isinstance(execution_store, DurableExecutionRecordStore):
            execution_store.recover()
    else:
        execution_store = ExecutionRecordStore()

    metrics_registry = MetricsRegistry()
    metrics_recorder = RuntimeMetricsRecorder(metrics_registry)
    trace_manager = TraceManager(trace_export or TraceExportConfig(exporter=TraceExporterType.MEMORY))
    replay_logger = StructuredLogger("replay")
    replay_events = ReplayEventEmitter(replay_logger, trace_recorder=trace_recorder)
    replay_engine = ReplayEngine(
        execution_store=execution_store,
        inspector=trace_inspector,
        replay_events=replay_events,
        submit_builder=submit_from_payload,
        runtime_repository=runtime_repository,
    )
    replay_debug = ReplayDebugService(replay_engine)
    stream_events = StreamEventEmitter(
        StructuredLogger("streaming"),
        trace_recorder=trace_recorder,
    )
    cp = create_cp(
        trace_recorder=trace_recorder,
        metrics_recorder=metrics_recorder,
        trace_manager=trace_manager,
    )
    adapter = create_adapter(
        trace_recorder=trace_recorder,
        metrics_recorder=metrics_recorder,
        trace_manager=trace_manager,
    )
    scheduler = create_scheduler(
        ControlPlaneQueueReader(cp.queue),
        adapter_client=EmbeddedAdapterClient(adapter),
        trace_recorder=trace_recorder,
        metrics_recorder=metrics_recorder,
        trace_manager=trace_manager,
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
        trace_manager=trace_manager,
        execution_store=execution_store,
        replay_engine=replay_engine,
        replay_debug=replay_debug,
        runtime_repository=runtime_repository,
        stream_events=stream_events,
    )
