"""Routing policy implementations. Owner: control plane."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from common_schemas.inference_request import ModelRecord
from common_schemas.routing import (
    LatencyTier,
    QualityTier,
    RoutingCandidate,
    RoutingDecision,
    RoutingPolicyName,
    RoutingResult,
    RoutableBackendSnapshot,
    new_route_id,
)


class RoutingPolicy(Protocol):
    name: str

    def select(
        self,
        *,
        request_id: UUID,
        model: ModelRecord,
        backends: tuple[RoutableBackendSnapshot, ...],
        excluded_backend_ids: frozenset[str] = frozenset(),
    ) -> RoutingResult: ...


def _filter_candidates(
    model: ModelRecord,
    backends: tuple[RoutableBackendSnapshot, ...],
    *,
    excluded: frozenset[str] = frozenset(),
) -> list[RoutingCandidate]:
    candidates: list[RoutingCandidate] = []
    for backend in backends:
        if backend.backend_id in excluded:
            continue
        supports = model.model_id in backend.supported_models or not backend.supported_models
        candidates.append(
            RoutingCandidate(
                backend_id=backend.backend_id,
                model_id=model.model_id,
                latency_tier=backend.latency_tier,
                quality_tier=backend.quality_tier,
                healthy=backend.healthy,
                supports_model=supports,
                available_capacity=backend.max_batch_size,
            )
        )
    return candidates


def _healthy_supporting(candidates: list[RoutingCandidate]) -> list[RoutingCandidate]:
    return [c for c in candidates if c.healthy and c.supports_model]


class ExplicitModelPolicy:
    name = RoutingPolicyName.EXPLICIT.value

    def select(
        self,
        *,
        request_id: UUID,
        model: ModelRecord,
        backends: tuple[RoutableBackendSnapshot, ...],
        excluded_backend_ids: frozenset[str] = frozenset(),
    ) -> RoutingResult:
        candidates = _filter_candidates(model, backends, excluded=excluded_backend_ids)
        target = model.backend
        for candidate in candidates:
            if candidate.backend_id == target and candidate.healthy and candidate.supports_model:
                decision = RoutingDecision(
                    route_id=new_route_id(),
                    request_id=request_id,
                    model_id=model.model_id,
                    backend_id=target,
                    policy_name=self.name,
                    reason="explicit_model_backend",
                )
                return RoutingResult(success=True, decision=decision, candidates=tuple(candidates))
        return RoutingResult(
            success=False,
            error=f"explicit backend unavailable: {target}",
            candidates=tuple(candidates),
        )


class LatencyTierPolicy:
    name = RoutingPolicyName.LATENCY_TIER.value

    def select(
        self,
        *,
        request_id: UUID,
        model: ModelRecord,
        backends: tuple[RoutableBackendSnapshot, ...],
        excluded_backend_ids: frozenset[str] = frozenset(),
    ) -> RoutingResult:
        candidates = _filter_candidates(model, backends, excluded=excluded_backend_ids)
        tier = model.capabilities.latency_tier
        eligible = [
            c for c in _healthy_supporting(candidates) if c.latency_tier == tier
        ]
        if not eligible:
            return RoutingResult(
                success=False,
                error=f"no healthy backend for latency_tier={tier.value}",
                candidates=tuple(candidates),
            )
        chosen = sorted(eligible, key=lambda c: c.backend_id)[0]
        decision = RoutingDecision(
            route_id=new_route_id(),
            request_id=request_id,
            model_id=model.model_id,
            backend_id=chosen.backend_id,
            policy_name=self.name,
            reason=f"latency_tier_match:{tier.value}",
        )
        return RoutingResult(success=True, decision=decision, candidates=tuple(candidates))


class QualityTierPolicy:
    name = RoutingPolicyName.QUALITY_TIER.value

    def select(
        self,
        *,
        request_id: UUID,
        model: ModelRecord,
        backends: tuple[RoutableBackendSnapshot, ...],
        excluded_backend_ids: frozenset[str] = frozenset(),
    ) -> RoutingResult:
        candidates = _filter_candidates(model, backends, excluded=excluded_backend_ids)
        tier = model.capabilities.quality_tier
        eligible = [
            c for c in _healthy_supporting(candidates) if c.quality_tier == tier
        ]
        if not eligible:
            return RoutingResult(
                success=False,
                error=f"no healthy backend for quality_tier={tier.value}",
                candidates=tuple(candidates),
            )
        chosen = sorted(eligible, key=lambda c: c.backend_id)[0]
        decision = RoutingDecision(
            route_id=new_route_id(),
            request_id=request_id,
            model_id=model.model_id,
            backend_id=chosen.backend_id,
            policy_name=self.name,
            reason=f"quality_tier_match:{tier.value}",
        )
        return RoutingResult(success=True, decision=decision, candidates=tuple(candidates))


class FallbackPolicy:
    """Wraps explicit selection with configured fallback backend."""

    name = RoutingPolicyName.FALLBACK.value

    def __init__(self, inner: RoutingPolicy | None = None) -> None:
        self._inner = inner or ExplicitModelPolicy()

    def select(
        self,
        *,
        request_id: UUID,
        model: ModelRecord,
        backends: tuple[RoutableBackendSnapshot, ...],
        excluded_backend_ids: frozenset[str] = frozenset(),
    ) -> RoutingResult:
        primary = self._inner.select(
            request_id=request_id,
            model=model,
            backends=backends,
            excluded_backend_ids=excluded_backend_ids,
        )
        if primary.success and primary.decision is not None:
            return primary

        fallback_id = model.fallback_backend
        if fallback_id is None:
            return RoutingResult(
                success=False,
                error=primary.error or "no fallback configured",
                candidates=primary.candidates,
            )

        candidates = _filter_candidates(model, backends, excluded=excluded_backend_ids)
        for candidate in candidates:
            if (
                candidate.backend_id == fallback_id
                and candidate.healthy
                and candidate.supports_model
            ):
                decision = RoutingDecision(
                    route_id=new_route_id(),
                    request_id=request_id,
                    model_id=model.model_id,
                    backend_id=fallback_id,
                    policy_name=self.name,
                    fallback_used=True,
                    primary_backend_id=model.backend,
                    reason="fallback_backend_selected",
                )
                return RoutingResult(success=True, decision=decision, candidates=tuple(candidates))

        return RoutingResult(
            success=False,
            error=f"fallback backend unavailable: {fallback_id}",
            candidates=tuple(candidates),
        )


def policy_for_model(model: ModelRecord) -> RoutingPolicy:
    if model.routing_policy == RoutingPolicyName.LATENCY_TIER:
        return LatencyTierPolicy()
    if model.routing_policy == RoutingPolicyName.QUALITY_TIER:
        return QualityTierPolicy()
    if model.routing_policy == RoutingPolicyName.FALLBACK:
        return FallbackPolicy()
    return ExplicitModelPolicy()
