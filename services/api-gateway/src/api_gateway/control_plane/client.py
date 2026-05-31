"""Control plane interface. No HTTP implementation in Session 4."""

from __future__ import annotations

from typing import Protocol

from common_schemas.inference_request import ModelRecord


class ControlPlaneClient(Protocol):
    async def get_model(self, model_id: str) -> ModelRecord | None:
        """Return model record or None if unknown."""

    async def is_ready(self) -> bool:
        """True when registry is available for lookups."""
