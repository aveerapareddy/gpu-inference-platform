"""Control plane application lifecycle."""

from __future__ import annotations

from dataclasses import dataclass

from gpu_inference_observability import StructuredLogger
from gpu_inference_observability.runtime.recorder import RuntimeEventRecorder

from control_plane.admission.framework import AdmissionFramework
from control_plane.config import Settings, get_settings
from control_plane.lifecycle.manager import LifecycleManager
from control_plane.queue.capacity import QueueCapacityConfig
from control_plane.queue.service import QueueService
from control_plane.queue.waiting_queue import QueueOperations
from control_plane.observability.events import LifecycleEventEmitter
from control_plane.registry.memory import InMemoryRequestRegistry
from control_plane.registry.queries import RegistryQueries
from control_plane.scheduler.client import SchedulerClient
from control_plane.scheduler.stub import StubSchedulerClient


@dataclass
class ControlPlaneApplication:
    settings: Settings
    logger: StructuredLogger
    registry: InMemoryRequestRegistry
    admission: AdmissionFramework
    scheduler: SchedulerClient
    events: LifecycleEventEmitter
    lifecycle: LifecycleManager
    queries: RegistryQueries
    queue: QueueService
    _running: bool = False

    async def startup(self) -> None:
        if self._running:
            return
        self.logger.info(
            "control plane starting",
            registry_max_entries=self.settings.registry_max_entries,
        )
        self._running = True
        self.logger.info(
            "control plane ready",
            registry_count=self.registry.count(),
            queue_depth=self.queue.depth(),
        )

    async def shutdown(self) -> None:
        if not self._running:
            return
        self.logger.info("control plane shutting down", registry_count=self.registry.count())
        self._running = False
        self.logger.info("control plane stopped")

    @property
    def is_running(self) -> bool:
        return self._running


def create_application(
    settings: Settings | None = None,
    *,
    trace_recorder: RuntimeEventRecorder | None = None,
) -> ControlPlaneApplication:
    settings = settings or get_settings()
    logger = StructuredLogger(settings.service_name)
    registry = InMemoryRequestRegistry(max_entries=settings.registry_max_entries)
    admission = AdmissionFramework()
    scheduler: SchedulerClient = StubSchedulerClient()
    events = LifecycleEventEmitter(logger, settings.service_name, trace_recorder=trace_recorder)
    queue_config = QueueCapacityConfig(
        max_queue_size=settings.max_queue_size,
        queue_timeout_ms=settings.queue_timeout_ms,
    )
    queue_ops = QueueOperations(queue_config)
    queue = QueueService(registry, queue_ops, events)
    lifecycle = LifecycleManager(registry, admission, scheduler, events, queue)
    queries = RegistryQueries(registry)
    return ControlPlaneApplication(
        settings=settings,
        logger=logger,
        registry=registry,
        admission=admission,
        scheduler=scheduler,
        events=events,
        lifecycle=lifecycle,
        queries=queries,
        queue=queue,
    )
