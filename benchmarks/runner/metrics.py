"""Benchmark metrics aggregation. Owner: benchmarks.runner."""

from __future__ import annotations

from benchmarks.runner.models import BenchmarkResult, BenchmarkSummary


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = int(round((pct / 100.0) * (len(ordered) - 1)))
    return ordered[max(0, min(index, len(ordered) - 1))]


def build_summary(
    results: tuple[BenchmarkResult, ...],
    *,
    duration_seconds: float,
) -> BenchmarkSummary:
    successes = [r for r in results if r.success]
    failures = [r for r in results if not r.success]
    latencies = [r.latency_ms for r in successes if r.latency_ms is not None]
    ttfts = [r.ttft_ms for r in successes if r.ttft_ms is not None]
    itls = [v for r in successes for v in r.itl_ms_samples]
    queue_waits = [r.queue_wait_ms for r in successes if r.queue_wait_ms is not None]
    gpu_utils = [r.gpu_utilization_percent for r in successes if r.gpu_utilization_percent is not None]
    gpu_mem = [r.gpu_memory_used_bytes for r in successes if r.gpu_memory_used_bytes is not None]

    throughput = None
    if duration_seconds > 0 and successes:
        throughput = len(successes) / duration_seconds

    return BenchmarkSummary(
        total_requests=len(results),
        successful_requests=len(successes),
        failed_requests=len(failures),
        throughput_rps=throughput,
        latency_ms_p50=_percentile(latencies, 50.0),
        latency_ms_p95=_percentile(latencies, 95.0),
        latency_ms_p99=_percentile(latencies, 99.0),
        ttft_ms_p50=_percentile(ttfts, 50.0),
        ttft_ms_p95=_percentile(ttfts, 95.0),
        ttft_ms_p99=_percentile(ttfts, 99.0),
        itl_ms_p50=_percentile(itls, 50.0),
        itl_ms_p95=_percentile(itls, 95.0),
        queue_wait_ms_p50=_percentile(queue_waits, 50.0),
        gpu_utilization_percent_p50=_percentile(gpu_utils, 50.0),
        gpu_memory_used_bytes_p50=(
            int(_percentile([float(v) for v in gpu_mem], 50.0))
            if gpu_mem
            else None
        ),
        duration_seconds=duration_seconds,
    )


def snapshot_prometheus_metrics(export: str, metric_names: tuple[str, ...]) -> dict[str, float]:
    totals: dict[str, float] = {}
    for line in export.splitlines():
        if line.startswith("#"):
            continue
        for name in metric_names:
            if line.startswith(name):
                totals[name] = totals.get(name, 0.0) + float(line.split()[-1])
    return totals
