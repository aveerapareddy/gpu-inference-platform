"""Routing engine. Owner: control plane."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from common_schemas.routing import RoutingResult, RoutableBackendSnapshot
from control_plane.registry.model_registry import ModelRegistry
from control_plane.routing.events import RoutingEventEmitter, RoutingEventType
from control_plane.routing.policies import policy_for_model
from gpu_inference_observability.registry.recorder import RuntimeMetricsRecorder


class BackendSnapshotProvider(Protocol):
    def list_routable_backends(self) -> tuple[RoutableBackendSnapshot, ...]: ...


class RoutingEngine:
    """Deterministic model and backend selection."""

    def __init__(
        self,
        model_registry: ModelRegistry,
        backend_provider: BackendSnapshotProvider,
        *,
        events: RoutingEventEmitter | None = None,
        metrics_recorder: RuntimeMetricsRecorder | None = None,
    ) -> None:
        self._models = model_registry
        self._backends = backend_provider
        self._events = events
        self._metrics = metrics_recorder

    def route(
        self,
        *,
        request_id: UUID,
        model_id: str,
        excluded_backend_ids: frozenset[str] = frozenset(),
    ) -> RoutingResult:
        self._emit(RoutingEventType.ROUTING_STARTED, request_id=request_id, model_id=model_id)
        model = self._models.get_model(model_id)
        if model is None:
            result = RoutingResult(success=False, error=f"model unavailable: {model_id}")
            self._record_failure(request_id, model_id=model_id, error=result.error)
            return result

        self._emit(
            RoutingEventType.MODEL_SELECTED,
            request_id=request_id,
            model_id=model.model_id,
            extra={"routing_policy": model.routing_policy.value},
        )

        backends = self._backends.list_routable_backends()
        policy = policy_for_model(model)
        result = policy.select(
            request_id=request_id,
            model=model,
            backends=backends,
            excluded_backend_ids=excluded_backend_ids,
        )

        if not result.success or result.decision is None:
            self._record_failure(
                request_id,
                model_id=model_id,
                error=result.error or "routing_failed",
            )
            return result

        decision = result.decision
        if self._metrics is not None:
            self._metrics.record_routing_decision(model_id=model_id, backend_id=decision.backend_id)
            self._metrics.record_model_request(model_id=model_id)
            self._metrics.record_backend_selection(backend_id=decision.backend_id)
            if decision.fallback_used:
                self._metrics.record_fallback_invocation(model_id=model_id)

        if decision.fallback_used:
            self._emit(
                RoutingEventType.FALLBACK_INVOKED,
                request_id=request_id,
                route_id=decision.route_id,
                model_id=model_id,
                backend_id=decision.backend_id,
                extra={
                    "primary_backend_id": decision.primary_backend_id,
                    "reason": decision.reason,
                },
            )

        self._emit(
            RoutingEventType.BACKEND_SELECTED,
            request_id=request_id,
            route_id=decision.route_id,
            model_id=model_id,
            backend_id=decision.backend_id,
            extra={"policy_name": decision.policy_name, "reason": decision.reason},
        )
        self._emit(
            RoutingEventType.ROUTING_COMPLETED,
            request_id=request_id,
            route_id=decision.route_id,
            model_id=model_id,
            backend_id=decision.backend_id,
            extra={"fallback_used": decision.fallback_used},
        )
        return result

    def _record_failure(
        self,
        request_id: UUID,
        *,
        model_id: str,
        error: str,
    ) -> None:
        if self._metrics is not None:
            self._metrics.record_routing_failure(model_id=model_id)
        self._emit(
            RoutingEventType.ROUTING_FAILED,
            request_id=request_id,
            model_id=model_id,
            extra={"error": error},
        )

    def _emit(self, event_type: RoutingEventType, **kwargs) -> None:
        if self._events is None:
            return
        self._events.emit(event_type, **kwargs)
