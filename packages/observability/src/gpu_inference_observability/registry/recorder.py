"""Runtime metrics recording helpers."""

from __future__ import annotations

import threading
import time
from uuid import UUID

from gpu_inference_observability.registry.registry import MetricsRegistry


class RuntimeMetricsRecorder:
    """Records operational metrics into MetricsRegistry."""

    def __init__(self, registry: MetricsRegistry) -> None:
        self._registry = registry
        self._request_started: dict[UUID, float] = {}
        self._lock = threading.RLock()

    @property
    def registry(self) -> MetricsRegistry:
        return self._registry

    def record_request_received(self, request_id: UUID) -> None:
        self._registry.requests_received_total.inc()
        self._registry.active_requests.inc()
        with self._lock:
            self._request_started[request_id] = time.monotonic()

    def record_request_completed(self, request_id: UUID) -> None:
        self._registry.requests_completed_total.inc()
        self._finish_request(request_id)

    def record_request_failed(self, request_id: UUID) -> None:
        self._registry.requests_failed_total.inc()
        self._finish_request(request_id)

    def record_request_rejected(self, request_id: UUID) -> None:
        self._registry.requests_rejected_total.inc()
        self._finish_request(request_id)

    def set_queue_depth(self, depth: int) -> None:
        self._registry.queue_depth.set(depth)

    def record_queue_enqueue(self, *, wait_seconds: float | None = None) -> None:
        self._registry.queue_enqueue_total.inc()
        if wait_seconds is not None:
            self._registry.queue_wait_duration_seconds.observe(wait_seconds)

    def record_queue_dequeue(self, *, wait_seconds: float | None = None) -> None:
        self._registry.queue_dequeue_total.inc()
        if wait_seconds is not None:
            self._registry.queue_wait_duration_seconds.observe(wait_seconds)

    def record_queue_timeout(self, *, wait_seconds: float | None = None) -> None:
        self._registry.queue_timeout_total.inc()
        if wait_seconds is not None:
            self._registry.queue_wait_duration_seconds.observe(wait_seconds)

    def record_scheduler_cycle(
        self,
        *,
        selected_count: int,
        skipped_count: int,
        duration_seconds: float,
        failed: bool = False,
    ) -> None:
        self._registry.scheduler_cycles_total.inc()
        if selected_count:
            self._registry.scheduler_selection_total.inc(selected_count)
        if skipped_count:
            self._registry.scheduler_skip_total.inc(skipped_count)
        if failed:
            self._registry.scheduler_failures_total.inc()
        self._registry.scheduler_cycle_duration_seconds.observe(duration_seconds)

    def record_batch_created(self) -> None:
        self._registry.batches_created_total.inc()

    def set_active_batches(self, count: int) -> None:
        self._registry.active_batches.set(count)

    def record_batch_admission(self, *, size: int) -> None:
        self._registry.batch_admissions_total.inc()
        self._registry.batch_size.observe(size)

    def record_batch_failed(self, *, lifetime_seconds: float) -> None:
        self._registry.batch_failures_total.inc()
        self._registry.batch_lifetime_seconds.observe(lifetime_seconds)

    def record_batch_completed(self, *, lifetime_seconds: float) -> None:
        self._registry.batch_lifetime_seconds.observe(lifetime_seconds)

    def record_backend_submission(self, backend_id: str) -> None:
        self._registry.backend_submissions_total.labels(backend_id=backend_id).inc()

    def record_backend_acceptance(self, backend_id: str, *, duration_seconds: float) -> None:
        self._registry.backend_acceptance_total.labels(backend_id=backend_id).inc()
        self._registry.backend_request_duration_seconds.labels(backend_id=backend_id).observe(
            duration_seconds
        )

    def record_backend_rejection(self, backend_id: str, *, duration_seconds: float) -> None:
        self._registry.backend_rejections_total.labels(backend_id=backend_id).inc()
        self._registry.backend_request_duration_seconds.labels(backend_id=backend_id).observe(
            duration_seconds
        )

    def record_backend_failure(self, backend_id: str, *, duration_seconds: float) -> None:
        self._registry.backend_failures_total.labels(backend_id=backend_id).inc()
        self._registry.backend_request_duration_seconds.labels(backend_id=backend_id).observe(
            duration_seconds
        )

    def record_backend_tokens(
        self,
        backend_id: str,
        *,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> None:
        if prompt_tokens:
            self._registry.backend_prompt_tokens_total.labels(backend_id=backend_id).inc(prompt_tokens)
        if completion_tokens:
            self._registry.backend_completion_tokens_total.labels(backend_id=backend_id).inc(
                completion_tokens
            )

    def _finish_request(self, request_id: UUID) -> None:
        self._registry.active_requests.dec()
        with self._lock:
            started = self._request_started.pop(request_id, None)
        if started is not None:
            self._registry.request_duration_seconds.observe(time.monotonic() - started)
