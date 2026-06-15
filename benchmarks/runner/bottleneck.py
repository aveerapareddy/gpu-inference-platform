"""Bottleneck classification from measured telemetry. Owner: benchmarks.runner."""

from __future__ import annotations

from enum import StrEnum

from benchmarks.runner.models import BenchmarkRun, BottleneckAnalysis

KV_CACHE_PRESSURE_THRESHOLD = 0.85
GPU_UTILIZATION_THRESHOLD = 80.0
GPU_MEMORY_RATIO_THRESHOLD = 0.90
QUEUE_WAIT_DOMINANCE_RATIO = 0.50
SCHEDULER_DELAY_DOMINANCE_MS = 1.0


class BottleneckType(StrEnum):
    GPU_BOUND = "gpu_bound"
    MEMORY_BOUND = "memory_bound"
    KV_CACHE_BOUND = "kv_cache_bound"
    QUEUE_BOUND = "queue_bound"
    SCHEDULER_BOUND = "scheduler_bound"
    BACKEND_BOUND = "backend_bound"
    NONE_OBSERVED = "none_observed"


def _p50(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[len(ordered) // 2]


def _failure_categories(run: BenchmarkRun) -> dict[str, int]:
    counts: dict[str, int] = {}
    for result in run.results:
        if result.success:
            continue
        key = "unknown"
        error = (result.error or "").lower()
        if "queue" in error or "admission" in error:
            key = "queue"
        elif "batch" in error:
            key = "scheduler"
        elif "backend" in error:
            key = "backend"
        elif "not_placed" in error:
            key = "scheduler"
        counts[key] = counts.get(key, 0) + 1
    return counts


def analyze_bottleneck(run: BenchmarkRun) -> BottleneckAnalysis:
    summary = run.summary
    runtime = run.runtime_snapshot or {}
    evidence: list[str] = []
    classifications: dict[str, bool] = {t.value: False for t in BottleneckType if t != BottleneckType.NONE_OBSERVED}

    peak_kv = runtime.get("peak_kv_cache_occupancy_ratio")
    if peak_kv is None and summary is not None:
        peak_kv = summary.kv_cache_occupancy_ratio_p50
    if peak_kv is not None and peak_kv >= KV_CACHE_PRESSURE_THRESHOLD:
        classifications[BottleneckType.KV_CACHE_BOUND] = True
        evidence.append(f"peak_kv_cache_occupancy_ratio={peak_kv:.3f}")

    kv_events = runtime.get("kv_cache_pressure_events", 0)
    if isinstance(kv_events, (int, float)) and kv_events > 0:
        classifications[BottleneckType.KV_CACHE_BOUND] = True
        evidence.append(f"kv_cache_pressure_events={int(kv_events)}")

    gpu_util = runtime.get("peak_gpu_utilization_percent")
    if gpu_util is None and summary is not None:
        gpu_util = summary.gpu_utilization_percent_p50
    if gpu_util is not None and gpu_util >= GPU_UTILIZATION_THRESHOLD:
        classifications[BottleneckType.GPU_BOUND] = True
        evidence.append(f"peak_gpu_utilization_percent={gpu_util:.1f}")

    gpu_mem_ratio = runtime.get("peak_gpu_memory_ratio")
    if gpu_mem_ratio is not None and gpu_mem_ratio >= GPU_MEMORY_RATIO_THRESHOLD:
        classifications[BottleneckType.MEMORY_BOUND] = True
        evidence.append(f"peak_gpu_memory_ratio={gpu_mem_ratio:.3f}")

    queue_depth_peak = runtime.get("peak_queue_depth")
    if isinstance(queue_depth_peak, (int, float)) and queue_depth_peak > 0:
        queue_waits = [r.queue_wait_ms for r in run.results if r.queue_wait_ms is not None]
        latencies = [r.latency_ms for r in run.results if r.success and r.latency_ms is not None]
        qw_p50 = _p50(queue_waits)
        lat_p50 = _p50(latencies)
        if qw_p50 is not None and lat_p50 is not None and lat_p50 > 0 and (qw_p50 / lat_p50) >= QUEUE_WAIT_DOMINANCE_RATIO:
            classifications[BottleneckType.QUEUE_BOUND] = True
            evidence.append(f"queue_wait_p50_ms={qw_p50:.3f}")
            evidence.append(f"latency_p50_ms={lat_p50:.3f}")

    scheduling_delays = [r.scheduling_delay_ms for r in run.results if r.scheduling_delay_ms is not None]
    sched_p50 = _p50(scheduling_delays)
    if sched_p50 is not None and sched_p50 >= SCHEDULER_DELAY_DOMINANCE_MS:
        classifications[BottleneckType.SCHEDULER_BOUND] = True
        evidence.append(f"scheduling_delay_p50_ms={sched_p50:.3f}")

    cycle_ms = runtime.get("scheduler_cycle_duration_ms_p50")
    if isinstance(cycle_ms, (int, float)) and cycle_ms >= SCHEDULER_DELAY_DOMINANCE_MS:
        classifications[BottleneckType.SCHEDULER_BOUND] = True
        evidence.append(f"scheduler_cycle_duration_ms_p50={cycle_ms:.3f}")

    failures = _failure_categories(run)
    if failures.get("queue", 0) > 0:
        classifications[BottleneckType.QUEUE_BOUND] = True
        evidence.append(f"queue_related_failures={failures['queue']}")
    if failures.get("scheduler", 0) > 0:
        classifications[BottleneckType.SCHEDULER_BOUND] = True
        evidence.append(f"scheduler_related_failures={failures['scheduler']}")
    if failures.get("backend", 0) > 0:
        classifications[BottleneckType.BACKEND_BOUND] = True
        evidence.append(f"backend_related_failures={failures['backend']}")

    if summary is not None and summary.failed_requests > 0:
        evidence.append(f"failed_requests={summary.failed_requests}")

    priority = (
        BottleneckType.QUEUE_BOUND,
        BottleneckType.SCHEDULER_BOUND,
        BottleneckType.KV_CACHE_BOUND,
        BottleneckType.MEMORY_BOUND,
        BottleneckType.GPU_BOUND,
        BottleneckType.BACKEND_BOUND,
    )
    primary = BottleneckType.NONE_OBSERVED
    for candidate in priority:
        if classifications.get(candidate.value):
            primary = candidate
            break

    if not evidence and primary == BottleneckType.NONE_OBSERVED:
        evidence.append("no bottleneck signals above configured thresholds")

    return BottleneckAnalysis(
        primary_bottleneck=primary.value,
        classifications=classifications,
        evidence=tuple(evidence),
    )


def max_sustainable_concurrency(runs: list[BenchmarkRun]) -> int | None:
    """Highest concurrency with zero failed requests. Measured only."""
    sustainable = [r.scenario.concurrency for r in runs if r.summary and r.summary.failed_requests == 0]
    return max(sustainable) if sustainable else None
