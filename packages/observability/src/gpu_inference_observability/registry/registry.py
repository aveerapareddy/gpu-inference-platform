"""Centralized Prometheus metrics registry. Owner: gpu_inference_observability.registry."""

from __future__ import annotations

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest

PROMETHEUS_PREFIX = "gpu_inference"
CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"

# Histogram buckets for sub-second to multi-minute operations.
_DURATION_BUCKETS = (
    0.001,
    0.005,
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
    5.0,
    10.0,
    30.0,
    60.0,
    120.0,
)


class MetricsRegistry:
    """Source of truth for runtime Prometheus metrics."""

    def __init__(self, registry: CollectorRegistry | None = None) -> None:
        self._registry = registry or CollectorRegistry()

        self.requests_received_total = Counter(
            f"{PROMETHEUS_PREFIX}_requests_received_total",
            "Requests entering the control plane lifecycle",
            registry=self._registry,
        )
        self.requests_completed_total = Counter(
            f"{PROMETHEUS_PREFIX}_requests_completed_total",
            "Requests reaching COMPLETED state",
            registry=self._registry,
        )
        self.requests_failed_total = Counter(
            f"{PROMETHEUS_PREFIX}_requests_failed_total",
            "Requests reaching FAILED or TIMED_OUT state",
            registry=self._registry,
        )
        self.requests_rejected_total = Counter(
            f"{PROMETHEUS_PREFIX}_requests_rejected_total",
            "Requests reaching REJECTED state",
            registry=self._registry,
        )
        self.active_requests = Gauge(
            f"{PROMETHEUS_PREFIX}_active_requests",
            "Requests not in a terminal lifecycle state",
            registry=self._registry,
        )
        self.request_duration_seconds = Histogram(
            f"{PROMETHEUS_PREFIX}_request_duration_seconds",
            "Wall time from RECEIVED to terminal state",
            buckets=_DURATION_BUCKETS,
            registry=self._registry,
        )

        self.queue_depth = Gauge(
            f"{PROMETHEUS_PREFIX}_queue_depth",
            "Waiting queue depth",
            registry=self._registry,
        )
        self.queue_enqueue_total = Counter(
            f"{PROMETHEUS_PREFIX}_queue_enqueue_total",
            "Requests enqueued after admission",
            registry=self._registry,
        )
        self.queue_dequeue_total = Counter(
            f"{PROMETHEUS_PREFIX}_queue_dequeue_total",
            "Requests dequeued from waiting queue",
            registry=self._registry,
        )
        self.queue_timeout_total = Counter(
            f"{PROMETHEUS_PREFIX}_queue_timeout_total",
            "Requests expired due to queue wait timeout",
            registry=self._registry,
        )
        self.queue_wait_duration_seconds = Histogram(
            f"{PROMETHEUS_PREFIX}_queue_wait_duration_seconds",
            "Time spent waiting in queue before dequeue",
            buckets=_DURATION_BUCKETS,
            registry=self._registry,
        )

        self.scheduler_cycles_total = Counter(
            f"{PROMETHEUS_PREFIX}_scheduler_cycles_total",
            "Scheduler cycles executed",
            registry=self._registry,
        )
        self.scheduler_selection_total = Counter(
            f"{PROMETHEUS_PREFIX}_scheduler_selection_total",
            "Requests selected by scheduler in a cycle",
            registry=self._registry,
        )
        self.scheduler_skip_total = Counter(
            f"{PROMETHEUS_PREFIX}_scheduler_skip_total",
            "Requests skipped by scheduler in a cycle",
            registry=self._registry,
        )
        self.scheduler_failures_total = Counter(
            f"{PROMETHEUS_PREFIX}_scheduler_failures_total",
            "Scheduler cycle failures",
            registry=self._registry,
        )
        self.scheduler_cycle_duration_seconds = Histogram(
            f"{PROMETHEUS_PREFIX}_scheduler_cycle_duration_seconds",
            "Scheduler cycle wall time",
            buckets=_DURATION_BUCKETS,
            registry=self._registry,
        )

        self.batches_created_total = Counter(
            f"{PROMETHEUS_PREFIX}_batches_created_total",
            "Continuous batches created",
            registry=self._registry,
        )
        self.active_batches = Gauge(
            f"{PROMETHEUS_PREFIX}_active_batches",
            "Batches not in a terminal batch state",
            registry=self._registry,
        )
        self.batch_size = Histogram(
            f"{PROMETHEUS_PREFIX}_batch_size",
            "Active member count at batch admission",
            buckets=(1, 2, 4, 8, 16, 32, 64, 128),
            registry=self._registry,
        )
        self.batch_admissions_total = Counter(
            f"{PROMETHEUS_PREFIX}_batch_admissions_total",
            "Requests admitted into a batch",
            registry=self._registry,
        )
        self.batch_failures_total = Counter(
            f"{PROMETHEUS_PREFIX}_batch_failures_total",
            "Batches reaching FAILED state",
            registry=self._registry,
        )
        self.batch_lifetime_seconds = Histogram(
            f"{PROMETHEUS_PREFIX}_batch_lifetime_seconds",
            "Batch lifetime from creation to terminal state",
            buckets=_DURATION_BUCKETS,
            registry=self._registry,
        )

        self.backend_submissions_total = Counter(
            f"{PROMETHEUS_PREFIX}_backend_submissions_total",
            "Batch submissions to inference backend",
            ["backend_id"],
            registry=self._registry,
        )
        self.backend_acceptance_total = Counter(
            f"{PROMETHEUS_PREFIX}_backend_acceptance_total",
            "Backend batch acceptances",
            ["backend_id"],
            registry=self._registry,
        )
        self.backend_rejections_total = Counter(
            f"{PROMETHEUS_PREFIX}_backend_rejections_total",
            "Backend batch rejections",
            ["backend_id"],
            registry=self._registry,
        )
        self.backend_failures_total = Counter(
            f"{PROMETHEUS_PREFIX}_backend_failures_total",
            "Backend submission internal failures",
            ["backend_id"],
            registry=self._registry,
        )
        self.backend_request_duration_seconds = Histogram(
            f"{PROMETHEUS_PREFIX}_backend_request_duration_seconds",
            "Backend submit_batch call duration",
            ["backend_id"],
            buckets=_DURATION_BUCKETS,
            registry=self._registry,
        )
        self.request_ttft_seconds = Histogram(
            f"{PROMETHEUS_PREFIX}_request_ttft_seconds",
            "Time from request received to first streamed token",
            buckets=_DURATION_BUCKETS,
            registry=self._registry,
        )
        self.request_itl_seconds = Histogram(
            f"{PROMETHEUS_PREFIX}_request_itl_seconds",
            "Inter-token latency during streaming decode",
            buckets=_DURATION_BUCKETS,
            registry=self._registry,
        )
        self.streams_created_total = Counter(
            f"{PROMETHEUS_PREFIX}_streams_created_total",
            "Streaming sessions created",
            registry=self._registry,
        )
        self.streams_completed_total = Counter(
            f"{PROMETHEUS_PREFIX}_streams_completed_total",
            "Streaming sessions completed",
            registry=self._registry,
        )
        self.streams_failed_total = Counter(
            f"{PROMETHEUS_PREFIX}_streams_failed_total",
            "Streaming sessions failed",
            registry=self._registry,
        )
        self.streams_cancelled_total = Counter(
            f"{PROMETHEUS_PREFIX}_streams_cancelled_total",
            "Streaming sessions cancelled",
            registry=self._registry,
        )
        self.routing_decisions_total = Counter(
            f"{PROMETHEUS_PREFIX}_routing_decisions_total",
            "Routing decisions completed",
            ["model_id", "backend_id"],
            registry=self._registry,
        )
        self.routing_failures_total = Counter(
            f"{PROMETHEUS_PREFIX}_routing_failures_total",
            "Routing failures",
            ["model_id"],
            registry=self._registry,
        )
        self.fallback_invocations_total = Counter(
            f"{PROMETHEUS_PREFIX}_fallback_invocations_total",
            "Routing fallback invocations",
            ["model_id"],
            registry=self._registry,
        )
        self.model_requests_total = Counter(
            f"{PROMETHEUS_PREFIX}_model_requests_total",
            "Requests routed by model",
            ["model_id"],
            registry=self._registry,
        )
        self.backend_selection_total = Counter(
            f"{PROMETHEUS_PREFIX}_backend_selection_total",
            "Backend selections from routing",
            ["backend_id"],
            registry=self._registry,
        )
        self.backend_prompt_tokens_total = Counter(
            f"{PROMETHEUS_PREFIX}_backend_prompt_tokens_total",
            "Prompt tokens returned by inference backend",
            ["backend_id"],
            registry=self._registry,
        )
        self.backend_completion_tokens_total = Counter(
            f"{PROMETHEUS_PREFIX}_backend_completion_tokens_total",
            "Completion tokens returned by inference backend",
            ["backend_id"],
            registry=self._registry,
        )

    def export_prometheus(self) -> bytes:
        return generate_latest(self._registry)
