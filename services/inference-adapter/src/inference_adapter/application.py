"""Inference adapter application lifecycle."""

from __future__ import annotations

import time
from dataclasses import dataclass
from uuid import UUID

from common_schemas.batch import Batch as DispatchBatch
from common_schemas.completion import InferenceCompletionRecord
from gpu_inference_observability import StructuredLogger
from gpu_inference_observability.runtime.recorder import RuntimeEventRecorder
from gpu_inference_observability.registry.recorder import RuntimeMetricsRecorder
from gpu_inference_observability.otel.helpers import optional_span
from gpu_inference_observability.otel.manager import TraceManager
from gpu_inference_observability.otel.spans import ComponentName, SpanName

from inference_adapter.backend.failures import (
    BackendInternalFailure,
    BackendMisconfigured,
    BackendRejected,
    BackendUnavailable,
)
from inference_adapter.backend.models import (
    BatchSubmitResult,
    CancelRequestResult,
    RequestCompletionResult,
    RequestStatusResult,
)
from inference_adapter.backend.state import BackendState
from inference_adapter.completion import to_completion_record
from inference_adapter.config import Settings, get_settings
from inference_adapter.observability.events import BackendEventEmitter, BackendEventType
from inference_adapter.registry.registry import BackendRegistry, RegisteredBackend


@dataclass
class InferenceAdapterApplication:
    settings: Settings
    logger: StructuredLogger
    registry: BackendRegistry
    events: BackendEventEmitter
    metrics_recorder: RuntimeMetricsRecorder | None = None
    trace_manager: TraceManager | None = None
    _running: bool = False

    async def startup(self) -> None:
        if self._running:
            return
        self.logger.info(
            "inference adapter starting",
            default_backend_id=self.settings.default_backend_id,
        )
        for entry in self.registry.list_backends():
            await self.refresh_backend_health(entry.backend.backend_id)
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
        supported_models: tuple[str, ...] | None = None,
        latency_tier=None,
        quality_tier=None,
        max_batch_size: int | None = None,
        metadata: dict | None = None,
    ) -> None:
        from common_schemas.routing import LatencyTier, QualityTier

        self.registry.register_backend(
            backend,
            initial_state=initial_state,
            supported_models=supported_models,
            latency_tier=latency_tier or LatencyTier.STANDARD,
            quality_tier=quality_tier or QualityTier.STANDARD,
            max_batch_size=max_batch_size,
            metadata=metadata,
        )
        self.events.emit(
            BackendEventType.BACKEND_REGISTERED,
            backend_id=backend.backend_id,
            reason="registered",
            extra={"initial_state": initial_state.value},
        )

    async def refresh_backend_health(self, backend_id: str) -> None:
        entry = self.registry.get_backend(backend_id)
        if entry is None:
            return
        health = await entry.backend.health_check()
        if health.state == "unavailable" or not health.healthy:
            target = BackendState.UNHEALTHY if health.state == "unavailable" else BackendState.DEGRADED
        else:
            target = BackendState.HEALTHY
        self.registry.set_state(backend_id, target)
        self.events.emit(
            BackendEventType.BACKEND_HEALTH_CHANGED,
            backend_id=backend_id,
            reason="health_check",
            extra={"state": target.value, "health_state": health.state, "health_message": health.message},
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

    def list_routable_backends(self):
        return self.registry.list_routable_snapshots()

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

        if self.metrics_recorder is not None:
            self.metrics_recorder.record_backend_submission(target_id)

        backend = entry.backend
        started = time.monotonic()
        with optional_span(
            self.trace_manager,
            SpanName.BACKEND_SUBMISSION,
            component=ComponentName.ADAPTER,
            batch_id=batch.batch_id,
            backend_id=target_id,
            model=batch.model,
        ) as backend_scope:
            for assignment in batch.assignments:
                backend_scope.set_request_context(
                    request_id=assignment.request_id,
                    correlation_id=self._correlation_for(assignment.request_id),
                    batch_id=batch.batch_id,
                    backend_id=target_id,
                )
            try:
                result = await backend.submit_batch(batch)
            except BackendRejected:
                if self.metrics_recorder is not None:
                    self.metrics_recorder.record_backend_rejection(
                        target_id,
                        duration_seconds=time.monotonic() - started,
                    )
                backend_scope.record_rejection("backend_rejected")
                raise
            except Exception as exc:
                if self.metrics_recorder is not None:
                    self.metrics_recorder.record_backend_failure(
                        target_id,
                        duration_seconds=time.monotonic() - started,
                    )
                backend_scope.record_exception(exc)
                raise BackendInternalFailure(
                    str(exc),
                    backend_id=target_id,
                    batch_id=str(batch.batch_id),
                ) from exc

            duration = time.monotonic() - started
            if result.accepted:
                if self.metrics_recorder is not None:
                    self.metrics_recorder.record_backend_acceptance(
                        target_id,
                        duration_seconds=duration,
                    )
                    for completion in result.completions:
                        self.metrics_recorder.record_backend_tokens(
                            target_id,
                            prompt_tokens=completion.prompt_tokens,
                            completion_tokens=completion.completion_tokens,
                        )
                backend_scope.set_attribute("accepted", True)
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
                if self.metrics_recorder is not None:
                    self.metrics_recorder.record_backend_rejection(
                        target_id,
                        duration_seconds=duration,
                    )
                backend_scope.record_rejection(result.reason or "batch_rejected")
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
        correlation_id = self._correlation_for(request_id)
        self.events.emit(
            event_type,
            backend_id=backend_id,
            batch_id=batch_id,
            request_id=request_id,
            correlation_id=correlation_id,
            reason=reason,
        )

    def _correlation_for(self, request_id: UUID) -> str | None:
        if self.events._recorder is not None:
            existing = self.events._recorder.store.get(request_id)
            if existing is not None:
                return existing.context.correlation_id
        return None

    async def get_request_completion(
        self,
        request_id: UUID,
        *,
        backend_id: str | None = None,
    ) -> InferenceCompletionRecord | None:
        target_id = backend_id or self.settings.default_backend_id
        backend = self.registry.get_backend_instance(target_id)
        if hasattr(backend, "get_request_completion"):
            result: RequestCompletionResult | None = await backend.get_request_completion(request_id)
            if result is None:
                return None
            return to_completion_record(result)
        return None

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
    metrics_recorder: RuntimeMetricsRecorder | None = None,
    trace_manager: TraceManager | None = None,
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
        metrics_recorder=metrics_recorder,
        trace_manager=trace_manager,
    )
    if settings.register_mock_backend:
        from inference_adapter.backends.mock import MockInferenceBackend

        app.register_backend(MockInferenceBackend(backend_id=settings.default_backend_id))
    if settings.register_vllm_backend:
        from inference_adapter.backends.vllm import VLLMBackend, VLLMBackendConfig

        app.register_backend(
            VLLMBackend(
                VLLMBackendConfig.from_values(
                    backend_id=settings.default_backend_id,
                    base_url=settings.vllm_base_url,
                    default_model=settings.vllm_model,
                    supported_models=settings.parsed_vllm_supported_models(),
                    max_batch_size=settings.vllm_max_batch_size,
                    request_timeout_seconds=settings.vllm_request_timeout_seconds,
                    health_timeout_seconds=settings.vllm_health_timeout_seconds,
                    api_key=settings.vllm_api_key,
                    tensor_parallel_size=settings.vllm_tensor_parallel_size,
                    gpu_memory_utilization=settings.vllm_gpu_memory_utilization,
                )
            )
        )
    return app
