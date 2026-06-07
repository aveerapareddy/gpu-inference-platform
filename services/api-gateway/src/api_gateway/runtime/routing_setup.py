"""Register multi-backend routing fixtures for embedded stack."""

from __future__ import annotations

from common_schemas.routing import LatencyTier, QualityTier
from inference_adapter.backends.mock import MockInferenceBackend


def register_routing_backends(adapter) -> None:
    """Register mock backends used by default model registry routing policies."""
    adapter.register_backend(
        MockInferenceBackend(backend_id="mock", supported_models=("demo", "example-model", "demo-fallback")),
        supported_models=("demo", "example-model", "demo-fallback"),
    )
    adapter.register_backend(
        MockInferenceBackend(backend_id="mock-fast", supported_models=("demo-fast",)),
        supported_models=("demo-fast",),
        latency_tier=LatencyTier.FAST,
    )
    adapter.register_backend(
        MockInferenceBackend(backend_id="mock-quality", supported_models=("demo-quality",)),
        supported_models=("demo-quality",),
        quality_tier=QualityTier.HIGH,
    )
    adapter.register_backend(
        MockInferenceBackend(backend_id="mock-primary", supported_models=("demo-fallback",), reject=True),
        supported_models=("demo-fallback",),
    )
