"""Dispatch result types."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BatchDispatchResult:
    batch_id: str
    backend_id: str
    accepted: bool
    reason: str
