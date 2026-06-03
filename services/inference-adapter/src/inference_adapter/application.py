"""Inference adapter application lifecycle."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from common_schemas.batch import Batch as DispatchBatch
from gpu_inference_observability import StructuredLogger
from gpu_inference_observability.runtime.recorder import RuntimeEventRecorder

from inference_adapter.backend.failures import (
    BackendInternalFailure,
    BackendMisconfigured,
    BackendRejected,
    BackendUnavailable,
)
from inference_adapter.backend.models import (
    BatchSubmitResult,
    CancelRequestResult,
    RequestStatusResult,
)
from inference_adapter.backend.state import BackendState
from inference_adapter.config import Settings, get_settings
from inference_adapter.observability.events import BackendEventEmitter, BackendEventType
from inference_adapter.registry.registry import BackendRegistry, RegisteredBackend


@dataclass
class InferenceAdapterApplication:
    settings: Settings
    logger: StructuredLogger
    registry: BackendRegistry
    events: BackendEventEmitter
    _running: bool = False

    async def startup(self) -> None:
        if self._running:
            return
        self.logger.info(
            "inference adapter starting",
            default_backend_id=self.settings.default_backend_id,
        )
        self._running = True
        self.logger.info(
            "inference adapter ready",
            backend_count=len(self.registry.list_backends()),
        )

    async def shutdown(self) -> None:
        if not self._running:
            return
        for entry in self.registry.list_backends():
            self.registry.set_state(entry.backend.backend_id, BackendState.STOPPED)
            self.events.emit(
                BackendEventType.BACKEND_HEALTH_CHANGED,
                backend_id=entry.backend.backend_id,
                reason="adapter_shutdown",
                extra={"state": BackendState.STOPPED.value},
            )
        self._running = False
        self.logger.info("inference adapter stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    def register_backend(
        self,
        backend,
        *,
        initial_state: BackendState = BackendState.STARTING,
    ) -> None:
        self.registry.register_backend(backend, initial_state=initial_state)
        self.events.emit(
            BackendEventType.BACKEND_REGISTERED,
            backend_id=backend.backend_id,
            reason="registered",
            extra={"initial_state": initial_state.value},
        )
        healthy_state = BackendState.HEALTHY if initial_state == BackendState.STARTING else initial_state
        if initial_state == BackendState.STARTING:
            self.registry.set_state(backend.backend_id, healthy_state)
            self.events.emit(
                BackendEventType.BACKEND_HEALTH_CHANGED,
                backend_id=backend.backend_id,
                reason="startup_health",
                extra={"state": healthy_state.value},
            )

    def remove_backend(self, backend_id: str) -> RegisteredBackend | None:
        removed = self.registry.remove_backend(backend_id)
        if removed is not None:
            self.events.emit(
                BackendEventType.BACKEND_REMOVED,
                backend_id=backend_id,
                reason="removed",
            )
        return removed

    def get_backend(self, backend_id: str) -> RegisteredBackend | None:
        return self.registry.get_backend(backend_id)

    def list_backends(self) -> list[RegisteredBackend]:
        return self.registry.list_backends()

    async def submit_batch(
        self,
        batch: DispatchBatch,
        *,
        backend_id: str | None = None,
    ) -> BatchSubmitResult:
        target_id = backend_id or self.settings.default_backend_id
        entry = self.registry.get_backend(target_id)
        if entry is None:
            raise BackendMisconfigured(f"backend not registered: {target_id}", backend_id=target_id)

        if entry.state in {BackendState.UNHEALTHY, BackendState.STOPPED}:
            raise BackendUnavailable(
                f"backend unavailable: {entry.state.value}",
                backend_id=target_id,
            )

        self.events.emit(
            BackendEventType.BACKEND_SELECTED,
            backend_id=target_id,
            batch_id=batch.batch_id,
            reason="explicit_backend_id",
        )
        self.events.emit(
            BackendEventType.BATCH_SUBMITTED,
            backend_id=target_id,
            batch_id=batch.batch_id,
            reason="submit_batch",
            extra={"assignment_count": len(batch.assignments)},
        )
        for assignment in batch.assignments:
            self._emit_request_backend_event(
                BackendEventType.BATCH_SUBMITTED,
                backend_id=target_id,
                batch_id=batch.batch_id,
                request_id=assignment.request_id,
                reason="submit_batch",
            )

        backend = entry.backend
        try:
            result = await backend.submit_batch(batch)
        except BackendRejected:
            raise
        except Exception as exc:
            raise BackendInternalFailure(
                str(exc),
                backend_id=target_id,
                batch_id=str(batch.batch_id),
            ) from exc

        if result.accepted:
            self.events.emit(
                BackendEventType.BATCH_ACCEPTED,
                backend_id=target_id,
                batch_id=batch.batch_id,
                reason=result.reason,
            )
            for assignment in batch.assignments:
                self._emit_request_backend_event(
                    BackendEventType.BATCH_ACCEPTED,
                    backend_id=target_id,
                    batch_id=batch.batch_id,
                    request_id=assignment.request_id,
                    reason=result.reason,
                )
        else:
            self.events.emit(
                BackendEventType.BATCH_REJECTED,
                backend_id=target_id,
                batch_id=batch.batch_id,
                reason=result.reason,
            )
            for assignment in batch.assignments:
                self._emit_request_backend_event(
                    BackendEventType.BATCH_REJECTED,
                    backend_id=target_id,
                    batch_id=batch.batch_id,
                    request_id=assignment.request_id,
                    reason=result.reason,
                )
        return result

    def _emit_request_backend_event(
        self,
        event_type: BackendEventType,
        *,
        backend_id: str,
        batch_id: UUID,
        request_id: UUID,
        reason: str | None = None,
    ) -> None:
        correlation_id: str | None = None
        if self.events._recorder is not None:
            existing = self.events._recorder.store.get(request_id)
            if existing is not None:
                correlation_id = existing.context.correlation_id
        self.events.emit(
            event_type,
            backend_id=backend_id,
            batch_id=batch_id,
            request_id=request_id,
            correlation_id=correlation_id,
            reason=reason,
        )

    async def get_request_status(
        self,
        request_id: UUID,
        *,
        backend_id: str | None = None,
    ) -> RequestStatusResult:
        target_id = backend_id or self.settings.default_backend_id
        backend = self.registry.get_backend_instance(target_id)
        return await backend.get_request_status(request_id)

    async def cancel_request(
        self,
        request_id: UUID,
        *,
        backend_id: str | None = None,
    ) -> CancelRequestResult:
        target_id = backend_id or self.settings.default_backend_id
        backend = self.registry.get_backend_instance(target_id)
        return await backend.cancel_request(request_id)


def create_application(
    settings: Settings | None = None,
    *,
    trace_recorder: RuntimeEventRecorder | None = None,
) -> InferenceAdapterApplication:
    settings = settings or get_settings()
    logger = StructuredLogger(settings.service_name)
    registry = BackendRegistry()
    events = BackendEventEmitter(logger, settings.service_name, trace_recorder=trace_recorder)
    app = InferenceAdapterApplication(
        settings=settings,
        logger=logger,
        registry=registry,
        events=events,
    )
    if settings.register_mock_backend:
        from inference_adapter.backends.mock import MockInferenceBackend

        app.register_backend(MockInferenceBackend(backend_id=settings.default_backend_id))
    return app
