"""In-memory model registry. Owner: control plane."""

from __future__ import annotations

import threading

from common_schemas.inference_request import ModelRecord
from common_schemas.routing import LatencyTier, ModelCapabilities, QualityTier, RoutingPolicyName


class ModelRegistry:
    """Source of truth for available models."""

    def __init__(self) -> None:
        self._models: dict[str, ModelRecord] = {}
        self._lock = threading.RLock()

    def register_model(self, record: ModelRecord) -> ModelRecord:
        with self._lock:
            self._models[record.model_id] = record
            return record

    def remove_model(self, model_id: str) -> ModelRecord | None:
        with self._lock:
            return self._models.pop(model_id, None)

    def list_models(self) -> list[ModelRecord]:
        with self._lock:
            return list(self._models.values())

    def get_model(self, model_id: str) -> ModelRecord | None:
        with self._lock:
            return self._models.get(model_id)


def default_model_registry() -> ModelRegistry:
    registry = ModelRegistry()
    registry.register_model(
        ModelRecord(
            model_id="demo",
            backend="mock",
            pool_id="default",
            max_output_tokens=1024,
            max_prompt_tokens=32768,
            default_temperature=1.0,
            routing_policy=RoutingPolicyName.EXPLICIT,
        )
    )
    registry.register_model(
        ModelRecord(
            model_id="example-model",
            backend="mock",
            pool_id="default",
            max_output_tokens=256,
            max_prompt_tokens=16384,
            routing_policy=RoutingPolicyName.EXPLICIT,
        )
    )
    registry.register_model(
        ModelRecord(
            model_id="demo-fast",
            backend="mock-fast",
            pool_id="latency",
            max_output_tokens=512,
            max_prompt_tokens=16384,
            routing_policy=RoutingPolicyName.LATENCY_TIER,
            capabilities=ModelCapabilities(latency_tier=LatencyTier.FAST),
        )
    )
    registry.register_model(
        ModelRecord(
            model_id="demo-quality",
            backend="mock-quality",
            pool_id="quality",
            max_output_tokens=1024,
            max_prompt_tokens=32768,
            routing_policy=RoutingPolicyName.QUALITY_TIER,
            capabilities=ModelCapabilities(quality_tier=QualityTier.HIGH),
        )
    )
    registry.register_model(
        ModelRecord(
            model_id="demo-fallback",
            backend="mock-primary",
            pool_id="default",
            max_output_tokens=512,
            max_prompt_tokens=16384,
            routing_policy=RoutingPolicyName.FALLBACK,
            fallback_backend="mock",
        )
    )
    return registry
