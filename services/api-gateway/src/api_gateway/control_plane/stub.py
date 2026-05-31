"""In-process control plane stub for gateway development."""

from __future__ import annotations

from common_schemas.inference_request import ModelRecord

from api_gateway.control_plane.client import ControlPlaneClient

_STUB_MODELS: dict[str, ModelRecord] = {
    "demo": ModelRecord(
        model_id="demo",
        backend="mock",
        pool_id="default",
        max_output_tokens=1024,
        max_prompt_tokens=32768,
        default_temperature=1.0,
    ),
    "example-model": ModelRecord(
        model_id="example-model",
        backend="mock",
        pool_id="default",
        max_output_tokens=256,
        max_prompt_tokens=16384,
    ),
}


class StubControlPlaneClient:
    """Planned replacement: HTTP client to services/control-plane."""

    async def get_model(self, model_id: str) -> ModelRecord | None:
        return _STUB_MODELS.get(model_id)

    async def is_ready(self) -> bool:
        return True
