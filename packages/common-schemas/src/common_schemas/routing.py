"""Routing domain types. Owner: control plane."""

from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class LatencyTier(StrEnum):
    FAST = "fast"
    STANDARD = "standard"
    SLOW = "slow"


class QualityTier(StrEnum):
    HIGH = "high"
    STANDARD = "standard"
    ECONOMY = "economy"


class RoutingPolicyName(StrEnum):
    EXPLICIT = "explicit"
    LATENCY_TIER = "latency_tier"
    QUALITY_TIER = "quality_tier"
    FALLBACK = "fallback"


class ModelCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    latency_tier: LatencyTier = LatencyTier.STANDARD
    quality_tier: QualityTier = QualityTier.STANDARD
    supports_streaming: bool = True


class RoutingCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    backend_id: str
    model_id: str
    score: float = 0.0
    latency_tier: LatencyTier | None = None
    quality_tier: QualityTier | None = None
    healthy: bool = True
    supports_model: bool = True
    available_capacity: int | None = None


class RoutingDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    route_id: UUID
    request_id: UUID
    model_id: str
    backend_id: str
    policy_name: str
    fallback_used: bool = False
    primary_backend_id: str | None = None
    reason: str


class RoutingResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    success: bool
    decision: RoutingDecision | None = None
    error: str | None = None
    candidates: tuple[RoutingCandidate, ...] = Field(default_factory=tuple)


class RoutableBackendSnapshot(BaseModel):
    """Adapter-provided backend view for routing. No backend implementation details."""

    model_config = ConfigDict(extra="forbid", strict=True)

    backend_id: str
    state: str
    healthy: bool
    supported_models: tuple[str, ...] = Field(default_factory=tuple)
    latency_tier: LatencyTier = LatencyTier.STANDARD
    quality_tier: QualityTier = QualityTier.STANDARD
    max_batch_size: int = Field(default=32, ge=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


def new_route_id() -> UUID:
    return uuid4()
