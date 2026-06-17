"""Shared stack builder and assertion helpers for reliability validation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from common_schemas.inference_request import InferenceRequest, Message, RequestContext, SubmitRequest
from common_schemas.states import MessageRole
from control_plane.config import Settings as CPSettings
from gpu_inference_observability.failure_injection.config import FailurePoint
from gpu_inference_observability.failure_injection.injector import FailureInjector
from gpu_inference_observability.otel.config import TraceExportConfig, TraceExporterType
from gpu_inference_observability.otel.manager import TraceManager
from gpu_inference_observability import StructuredLogger
from gpu_inference_observability.registry.recorder import RuntimeMetricsRecorder
from gpu_inference_observability.registry.registry import MetricsRegistry, PROMETHEUS_PREFIX
from gpu_inference_observability.runtime.inspection import TraceInspector
from gpu_inference_observability.runtime.recorder import RuntimeEventRecorder
from gpu_inference_observability.persistence.durable_store import DurableExecutionRecordStore
from gpu_inference_observability.persistence.events import PersistenceEventEmitter
from gpu_inference_observability.persistence.repository import RuntimeRepository
from gpu_inference_observability.persistence.sqlite.runtime_repository import SqliteRuntimeRepository
from gpu_inference_observability.runtime.replay.debugging import ReplayDebugService
from gpu_inference_observability.runtime.replay.engine import ReplayEngine
from gpu_inference_observability.runtime.replay.events import ReplayEventEmitter
from gpu_inference_observability.runtime.replay.store import ExecutionRecordStore
from gpu_inference_observability.runtime.store import RequestTraceStore
from inference_adapter.backend.failures import (
    BackendInternalFailure,
    BackendTimeout,
    BackendUnavailable,
)
from inference_adapter.backend.models import BatchSubmitResult
from inference_adapter.backends.mock import MockInferenceBackend
from inference_adapter.config import Settings as AdapterSettings

from api_gateway.runtime.orchestrator import RequestPathOrchestrator
from api_gateway.runtime.replay import submit_from_payload
from api_gateway.runtime.stack import PlatformStack
from control_plane.admission.framework import AdmissionFramework
from scheduler import ControlPlaneQueueReader, create_application as create_scheduler
from scheduler.config import Settings as SchedSettings
from scheduler.integrations.embedded_adapter import EmbeddedAdapterClient
from control_plane import create_application as create_cp
from inference_adapter import create_application as create_adapter


def submit_request(model: str = "demo") -> SubmitRequest:
    rid = uuid4()
    return SubmitRequest(
        inference_request=InferenceRequest(
            request_id=rid,
            model=model,
            messages=[Message(role=MessageRole.USER, content="reliability")],
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


def metric_value(export: str, name: str) -> float:
    total = 0.0
    for line in export.splitlines():
        if line.startswith("#") or not line.startswith(name):
            continue
        total += float(line.split()[-1])
    return total


def export_metrics(registry: MetricsRegistry) -> str:
    return registry.export_prometheus().decode()


class InjectableMockBackend(MockInferenceBackend):
    """Deterministic backend failure injection."""

    def __init__(
        self,
        injector: FailureInjector,
        backend_id: str = "mock",
        *,
        supported_models: tuple[str, ...] = ("demo",),
        max_batch_size: int = 32,
        reject: bool = False,
    ) -> None:
        super().__init__(
            backend_id=backend_id,
            supported_models=supported_models,
            max_batch_size=max_batch_size,
            reject=reject,
        )
        self._injector = injector

    async def submit_batch(self, batch):
        request_id = batch.assignments[0].request_id if batch.assignments else None
        if self._injector.should_inject(FailurePoint.BACKEND_UNAVAILABLE, request_id=request_id):
            raise BackendUnavailable(self._injector.config.message, backend_id=self.backend_id)
        if self._injector.should_inject(FailurePoint.BACKEND_TIMEOUT, request_id=request_id):
            raise BackendTimeout(self._injector.config.message, backend_id=self.backend_id)
        if self._injector.should_inject(FailurePoint.BACKEND_INTERNAL_ERROR, request_id=request_id):
            raise BackendInternalFailure(
                self._injector.config.message,
                backend_id=self.backend_id,
                batch_id=str(batch.batch_id),
            )
        if self._injector.should_inject(FailurePoint.BACKEND_REJECTION, request_id=request_id):
            now = datetime.now(timezone.utc)
            return BatchSubmitResult(
                batch_id=batch.batch_id,
                backend_id=self.backend_id,
                accepted=False,
                reason="injected_backend_rejection",
                submitted_at=now,
            )
        return await super().submit_batch(batch)


def force_queue_timeout(queue_ops, request_id: UUID) -> bool:
    with queue_ops._lock:
        for item in queue_ops._waiting.items:
            if item.request_id == request_id:
                item.queue_entered_at = datetime.now(timezone.utc) - timedelta(
                    milliseconds=queue_ops.config.queue_timeout_ms + 1000
                )
                return True
    return False


def corrupt_queue_without_lifecycle(queue_ops, request_id: UUID) -> bool:
    with queue_ops._lock:
        for index, item in enumerate(queue_ops._waiting.items):
            if item.request_id == request_id:
                queue_ops._waiting.items.pop(index)
                queue_ops._reindex_positions()
                return True
    return False


class ValidationStack:
    """Embedded stack with shared observability recorders."""

    def __init__(
        self,
        *,
        cp_settings: CPSettings | None = None,
        sched_settings: SchedSettings | None = None,
        adapter_settings: AdapterSettings | None = None,
        failure_injector: FailureInjector | None = None,
        backend: MockInferenceBackend | InjectableMockBackend | None = None,
        admission: AdmissionFramework | None = None,
        db_path: str | None = None,
        dispatch_min_members: int | None = None,
        scheduler_policy_id: str = "fifo",
    ) -> None:
        self.failure_injector = failure_injector or FailureInjector()
        self.trace_store = RequestTraceStore()
        self.trace_recorder = RuntimeEventRecorder(self.trace_store)
        self.trace_inspector = TraceInspector(self.trace_store)
        self.runtime_repository: RuntimeRepository | None = None
        persistence_events: PersistenceEventEmitter | None = None
        if db_path is not None:
            persistence_events = PersistenceEventEmitter(
                StructuredLogger("persistence"),
                trace_recorder=self.trace_recorder,
            )
            self.runtime_repository = SqliteRuntimeRepository(db_path, events=persistence_events)
            self.execution_store: ExecutionRecordStore = DurableExecutionRecordStore(
                self.runtime_repository,
                events=persistence_events,
            )
            if isinstance(self.execution_store, DurableExecutionRecordStore):
                self.execution_store.recover()
        else:
            self.execution_store = ExecutionRecordStore()
        self.metrics_registry = MetricsRegistry()
        self.metrics_recorder = RuntimeMetricsRecorder(self.metrics_registry)
        TraceManager.clear_collected_spans()
        self.trace_manager = TraceManager(TraceExportConfig(exporter=TraceExporterType.MEMORY))
        replay_events = ReplayEventEmitter(StructuredLogger("replay"), trace_recorder=self.trace_recorder)
        self.replay_engine = ReplayEngine(
            execution_store=self.execution_store,
            inspector=self.trace_inspector,
            replay_events=replay_events,
            submit_builder=submit_from_payload,
            runtime_repository=self.runtime_repository,
        )
        self.replay_debug = ReplayDebugService(self.replay_engine)

        cp_kwargs: dict = {
            "trace_recorder": self.trace_recorder,
            "metrics_recorder": self.metrics_recorder,
            "trace_manager": self.trace_manager,
        }
        if admission is not None:
            cp_kwargs["admission"] = admission
        self.cp = create_cp(cp_settings or CPSettings(max_queue_size=10, queue_timeout_ms=60_000), **cp_kwargs)
        self.adapter = create_adapter(
            adapter_settings or AdapterSettings(register_mock_backend=False),
            trace_recorder=self.trace_recorder,
            metrics_recorder=self.metrics_recorder,
            trace_manager=self.trace_manager,
        )
        if backend is not None:
            self.adapter.register_backend(backend)
        self.scheduler = create_scheduler(
            ControlPlaneQueueReader(self.cp.queue),
            sched_settings or SchedSettings(max_candidate_requests=5, max_batch_size=4, tick_interval_ms=60_000),
            adapter_client=EmbeddedAdapterClient(self.adapter),
            trace_recorder=self.trace_recorder,
            metrics_recorder=self.metrics_recorder,
            trace_manager=self.trace_manager,
            failure_injector=self.failure_injector,
            dispatch_min_members=dispatch_min_members,
            scheduler_policy_id=scheduler_policy_id,
        )
        self.stack = PlatformStack(
            control_plane=self.cp,
            scheduler=self.scheduler,
            adapter=self.adapter,
            trace_store=self.trace_store,
            trace_recorder=self.trace_recorder,
            trace_inspector=self.trace_inspector,
            metrics_registry=self.metrics_registry,
            metrics_recorder=self.metrics_recorder,
            trace_manager=self.trace_manager,
            execution_store=self.execution_store,
            replay_engine=self.replay_engine,
            replay_debug=self.replay_debug,
        )
        self.stack.runtime_repository = self.runtime_repository
        self.orchestrator = RequestPathOrchestrator(self.stack)

    async def startup(self) -> None:
        await self.stack.startup()

    async def shutdown(self) -> None:
        await self.stack.shutdown()
        self.trace_manager.force_flush()
        if self.runtime_repository is not None:
            self.runtime_repository.close()

    def metrics_export(self) -> str:
        return export_metrics(self.metrics_registry)

    def trace_failures(self, request_id: UUID):
        return self.trace_inspector.get_request_failures(request_id)
