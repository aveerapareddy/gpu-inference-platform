"""Concurrency scaling benchmark runner. Owner: benchmarks.runner."""

from __future__ import annotations

import time
from datetime import datetime, timezone

from gpu_inference_observability.gpu.collector import GPUMetricsCollector
from gpu_inference_observability.registry.registry import PROMETHEUS_PREFIX

from benchmarks.runner.batching_comparison import _schedule_and_complete_all
from benchmarks.runner.batching_modes import CONTINUOUS_BATCHING_MODE
from benchmarks.runner.bottleneck import analyze_bottleneck
from benchmarks.runner.context import StackRuntimeContext
from benchmarks.runner.embedded import _build_submit
from benchmarks.runner.metadata import capture_benchmark_environment, capture_hardware_metadata, capture_model_metadata
from benchmarks.runner.metrics import build_summary, snapshot_prometheus_metrics
from benchmarks.runner.models import BenchmarkRun, BenchmarkScenario, TelemetrySample
from benchmarks.runner.profiles import get_profile, prompt_for_profile
from benchmarks.runner.store import persist_run


def _metric_histogram_avg_ms(export: str, metric_prefix: str) -> float | None:
    sum_total = 0.0
    count_total = 0.0
    for line in export.splitlines():
        if line.startswith("#"):
            continue
        if line.startswith(f"{metric_prefix}_sum"):
            sum_total += float(line.split()[-1])
        if line.startswith(f"{metric_prefix}_count"):
            count_total += float(line.split()[-1])
    if count_total <= 0:
        return None
    return (sum_total / count_total) * 1000.0


def _count_capacity_events(trace_inspector, request_ids: list) -> int:
    count = 0
    for request_id in request_ids:
        timeline = trace_inspector.get_request_timeline(request_id)
        if timeline is None:
            continue
        for event in timeline.events:
            extra = event.extra or {}
            if extra.get("capacity_event") and event.event_type == "kv_cache_pressure_detected":
                count += 1
    return count


def _collect_sample(stack, gpu_collector: GPUMetricsCollector) -> TelemetrySample:
    snapshot = gpu_collector.collect()
    device = snapshot.devices[0] if snapshot.devices else None
    return TelemetrySample(
        captured_at=datetime.now(timezone.utc),
        queue_depth=stack.cp.queue.depth(),
        active_requests=len(stack.cp.registry.list_active()),
        active_sequences=snapshot.kv_cache.active_sequences,
        kv_cache_occupancy_ratio=snapshot.kv_cache.cache_occupancy_ratio,
        estimated_kv_bytes=snapshot.kv_cache.estimated_kv_bytes,
        gpu_utilization_percent=device.utilization_percent if device else None,
        gpu_memory_used_bytes=device.memory_used_bytes if device else None,
        scheduler_total_cycles=stack.scheduler.state.total_cycles,
    )


def _build_runtime_snapshot(
    *,
    samples: list[TelemetrySample],
    metrics_delta: dict[str, float],
    export: str,
    trace_inspector,
    hardware,
    request_ids: list,
) -> dict:
    peak_queue = max((s.queue_depth for s in samples), default=0)
    peak_kv = max((s.kv_cache_occupancy_ratio for s in samples), default=0.0)
    peak_active_seq = max((s.active_sequences for s in samples), default=0)
    peak_gpu_util = max((s.gpu_utilization_percent or 0.0 for s in samples), default=0.0)
    peak_gpu_mem = max((s.gpu_memory_used_bytes or 0 for s in samples), default=0)
    gpu_mem_ratio = None
    if hardware.gpu_memory_total_bytes and hardware.gpu_memory_total_bytes > 0:
        gpu_mem_ratio = peak_gpu_mem / hardware.gpu_memory_total_bytes

    cycle_prefix = f"{PROMETHEUS_PREFIX}_scheduler_cycle_duration_seconds"
    return {
        "peak_queue_depth": peak_queue,
        "peak_kv_cache_occupancy_ratio": peak_kv,
        "peak_active_sequences": peak_active_seq,
        "peak_gpu_utilization_percent": peak_gpu_util,
        "peak_gpu_memory_used_bytes": peak_gpu_mem,
        "peak_gpu_memory_ratio": gpu_mem_ratio,
        "scheduler_total_cycles": metrics_delta.get(f"{PROMETHEUS_PREFIX}_scheduler_cycles_total", 0.0),
        "scheduler_cycle_duration_ms_p50": _metric_histogram_avg_ms(export, cycle_prefix),
        "kv_cache_pressure_events": _count_capacity_events(trace_inspector, request_ids),
        "telemetry_sample_count": len(samples),
    }


async def run_scaling_experiment(
    stack,
    scenario: BenchmarkScenario,
    *,
    results_dir=None,
    persist: bool = True,
) -> BenchmarkRun:
    profile = get_profile(scenario.workload_profile)
    prompt = prompt_for_profile(profile)
    hardware = capture_hardware_metadata()
    model_meta = capture_model_metadata(model_id="demo", backend_id="mock", stream=True)
    environment = capture_benchmark_environment(model_id="demo", backend_id="mock", stream=True)

    gpu_collector = GPUMetricsCollector(
        metrics_recorder=stack.metrics_recorder,
        context_provider=StackRuntimeContext(stack),
    )

    metric_names = (
        f"{PROMETHEUS_PREFIX}_requests_completed_total",
        f"{PROMETHEUS_PREFIX}_requests_failed_total",
        f"{PROMETHEUS_PREFIX}_scheduler_cycles_total",
        f"{PROMETHEUS_PREFIX}_queue_depth",
    )

    started_at = datetime.now(timezone.utc)
    wall_start = time.perf_counter()

    await stack.startup()
    pre_metrics = snapshot_prometheus_metrics(stack.metrics_export(), metric_names)
    samples: list[TelemetrySample] = [ _collect_sample(stack, gpu_collector) ]

    submits = [
        _build_submit(model="demo", prompt=prompt, max_tokens=profile.max_tokens, stream=True)
        for _ in range(scenario.request_count)
    ]

    for submit in submits:
        await stack.orchestrator.lifecycle.process_through_queued(submit)

    def _on_complete(_result) -> None:
        samples.append(_collect_sample(stack, gpu_collector))

    results = await _schedule_and_complete_all(
        stack, submits, profile, gpu_collector, on_request_complete=_on_complete
    )
    samples.append(_collect_sample(stack, gpu_collector))

    duration = time.perf_counter() - wall_start
    export = stack.metrics_export()
    post_metrics = snapshot_prometheus_metrics(export, metric_names)
    metrics_delta = {k: post_metrics.get(k, 0.0) - pre_metrics.get(k, 0.0) for k in metric_names}

    runtime_snapshot = _build_runtime_snapshot(
        samples=samples,
        metrics_delta=metrics_delta,
        export=export,
        trace_inspector=stack.trace_inspector,
        hardware=hardware,
        request_ids=[s.inference_request.request_id for s in submits],
    )

    await stack.shutdown()

    ordered = tuple(sorted(results, key=lambda r: r.request_index))
    summary = build_summary(ordered, duration_seconds=duration)

    run = BenchmarkRun(
        scenario=scenario,
        environment=environment,
        hardware=hardware,
        model=model_meta,
        started_at=started_at,
        completed_at=datetime.now(timezone.utc),
        results=ordered,
        summary=summary,
        metrics_snapshot=metrics_delta,
        runner="scaling",
        batching_mode=CONTINUOUS_BATCHING_MODE.mode_id,
        batching_config=CONTINUOUS_BATCHING_MODE.to_config_dict(),
        runtime_snapshot=runtime_snapshot,
        telemetry_samples=tuple(samples),
    )
    run = run.model_copy(update={"bottleneck": analyze_bottleneck(run)})

    if persist:
        persist_run(run, results_dir=results_dir)
    return run
