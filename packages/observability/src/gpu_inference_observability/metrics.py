"""Metric name and kind contracts.

Status: Implemented (Session 3). No Prometheus client; names only.
Full catalog: docs/contracts/observability-metrics.md
"""

from __future__ import annotations

from enum import StrEnum


class MetricKind(StrEnum):
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"


class MetricName(StrEnum):
    """Prometheus-compatible names. Prefix gpu_inference_ applied at export time."""

    # Request
    REQUEST_TOTAL = "request_total"
    REQUEST_TTFT_SECONDS = "request_ttft_seconds"
    REQUEST_ITL_SECONDS = "request_itl_seconds"
    REQUEST_QUEUE_WAIT_SECONDS = "request_queue_wait_seconds"
    REQUEST_SCHEDULING_SECONDS = "request_scheduling_seconds"
    REQUEST_COMPLETION_SECONDS = "request_completion_seconds"
    REQUEST_TOKENS_GENERATED_TOTAL = "request_tokens_generated_total"
    REQUEST_CANCELLED_TOTAL = "request_cancelled_total"
    REQUEST_FAILED_TOTAL = "request_failed_total"

    # Batch
    BATCH_SIZE = "batch_size"
    BATCH_PREFILL_SECONDS = "batch_prefill_seconds"
    BATCH_DECODE_STEPS_TOTAL = "batch_decode_steps_total"
    BATCH_SLOTS_ACTIVE = "batch_slots_active"
    BATCH_DROPPED_SEQUENCES_TOTAL = "batch_dropped_sequences_total"

    # System
    SCHEDULER_QUEUE_DEPTH = "scheduler_queue_depth"
    SCHEDULER_ADMISSION_TOTAL = "scheduler_admission_total"
    SCHEDULER_DISPATCH_TOTAL = "scheduler_dispatch_total"
    GATEWAY_REQUESTS_TOTAL = "gateway_requests_total"
    CONTROL_PLANE_LOOKUP_TOTAL = "control_plane_lookup_total"
    WORKER_UP = "worker_up"
    WORKER_FAILURES_TOTAL = "worker_failures_total"
    SCHEDULER_STATE = "scheduler_state"
    THROUGHPUT_TOKENS_PER_SECOND = "throughput_tokens_per_second"

    # GPU
    GPU_UTILIZATION_RATIO = "gpu_utilization_ratio"
    GPU_MEMORY_USED_BYTES = "gpu_memory_used_bytes"
    GPU_MEMORY_UTILIZATION_RATIO = "gpu_memory_utilization_ratio"
    INFERENCE_PREFILL_SECONDS = "inference_prefill_seconds"
    INFERENCE_DECODE_STEP_SECONDS = "inference_decode_step_seconds"


METRIC_DEFINITIONS: dict[MetricName, MetricKind] = {
    MetricName.REQUEST_TOTAL: MetricKind.COUNTER,
    MetricName.REQUEST_TTFT_SECONDS: MetricKind.HISTOGRAM,
    MetricName.REQUEST_ITL_SECONDS: MetricKind.HISTOGRAM,
    MetricName.REQUEST_QUEUE_WAIT_SECONDS: MetricKind.HISTOGRAM,
    MetricName.REQUEST_SCHEDULING_SECONDS: MetricKind.HISTOGRAM,
    MetricName.REQUEST_COMPLETION_SECONDS: MetricKind.HISTOGRAM,
    MetricName.REQUEST_TOKENS_GENERATED_TOTAL: MetricKind.COUNTER,
    MetricName.REQUEST_CANCELLED_TOTAL: MetricKind.COUNTER,
    MetricName.REQUEST_FAILED_TOTAL: MetricKind.COUNTER,
    MetricName.BATCH_SIZE: MetricKind.HISTOGRAM,
    MetricName.BATCH_PREFILL_SECONDS: MetricKind.HISTOGRAM,
    MetricName.BATCH_DECODE_STEPS_TOTAL: MetricKind.COUNTER,
    MetricName.BATCH_SLOTS_ACTIVE: MetricKind.GAUGE,
    MetricName.BATCH_DROPPED_SEQUENCES_TOTAL: MetricKind.COUNTER,
    MetricName.SCHEDULER_QUEUE_DEPTH: MetricKind.GAUGE,
    MetricName.SCHEDULER_ADMISSION_TOTAL: MetricKind.COUNTER,
    MetricName.SCHEDULER_DISPATCH_TOTAL: MetricKind.COUNTER,
    MetricName.GATEWAY_REQUESTS_TOTAL: MetricKind.COUNTER,
    MetricName.CONTROL_PLANE_LOOKUP_TOTAL: MetricKind.COUNTER,
    MetricName.WORKER_UP: MetricKind.GAUGE,
    MetricName.WORKER_FAILURES_TOTAL: MetricKind.COUNTER,
    MetricName.SCHEDULER_STATE: MetricKind.GAUGE,
    MetricName.THROUGHPUT_TOKENS_PER_SECOND: MetricKind.GAUGE,
    MetricName.GPU_UTILIZATION_RATIO: MetricKind.GAUGE,
    MetricName.GPU_MEMORY_USED_BYTES: MetricKind.GAUGE,
    MetricName.GPU_MEMORY_UTILIZATION_RATIO: MetricKind.GAUGE,
    MetricName.INFERENCE_PREFILL_SECONDS: MetricKind.HISTOGRAM,
    MetricName.INFERENCE_DECODE_STEP_SECONDS: MetricKind.HISTOGRAM,
}

PROMETHEUS_PREFIX = "gpu_inference"


def prometheus_name(name: MetricName) -> str:
    return f"{PROMETHEUS_PREFIX}_{name.value}"
