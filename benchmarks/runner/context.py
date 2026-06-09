"""Runtime context for GPU metrics during embedded benchmarks."""

from __future__ import annotations


class StackRuntimeContext:
    """Reads active request and batch counts from an embedded ValidationStack."""

    def __init__(self, stack) -> None:
        self._stack = stack

    def active_requests(self) -> int:
        return len(self._stack.cp.registry.list_active())

    def active_sequences(self) -> int:
        stats = self._stack.scheduler.batch.get_batch_statistics()
        return stats.total_active_requests

    def active_batches(self) -> int:
        stats = self._stack.scheduler.batch.get_batch_statistics()
        return stats.active_batches

    def max_concurrent_sequences(self) -> int:
        return self._stack.scheduler.settings.max_candidate_requests

    def max_batch_slots(self) -> int:
        return self._stack.scheduler.settings.max_batch_size
