"""Runtime context for GPU observability collection."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PlatformRuntimeContext:
    control_plane: object
    scheduler: object
    max_sequences: int = 32
    max_batch_slot_limit: int = 32

    def active_requests(self) -> int:
        return len(self.control_plane.queries.list_active())

    def active_sequences(self) -> int:
        stats = self.scheduler.batch.get_batch_statistics()
        return stats.total_active_requests

    def active_batches(self) -> int:
        stats = self.scheduler.batch.get_batch_statistics()
        return stats.active_batches

    def max_concurrent_sequences(self) -> int:
        return self.max_sequences

    def max_batch_slots(self) -> int:
        return self.max_batch_slot_limit
