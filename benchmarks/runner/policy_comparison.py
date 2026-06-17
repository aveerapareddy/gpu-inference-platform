"""Scheduler policy comparison runner. Owner: benchmarks.runner."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from common_schemas.inference_request import InferenceRequest, Message, RequestContext, SubmitRequest
from common_schemas.states import MessageRole, PriorityClass

from benchmarks.runner.batching_comparison import _schedule_and_complete_all
from benchmarks.runner.batching_modes import CONTINUOUS_BATCHING_MODE
from benchmarks.runner.context import StackRuntimeContext
from benchmarks.runner.metadata import capture_benchmark_environment, capture_hardware_metadata, capture_model_metadata
from benchmarks.runner.metrics import build_summary, snapshot_prometheus_metrics
from benchmarks.runner.models import BenchmarkRun, BenchmarkScenario
from benchmarks.runner.profiles import get_profile, prompt_for_profile
from benchmarks.runner.scheduler_policies import SchedulerPolicyMode
from benchmarks.runner.store import persist_run
from gpu_inference_observability.gpu.collector import GPUMetricsCollector
from gpu_inference_observability.registry.registry import PROMETHEUS_PREFIX

_PRIORITY_CYCLE: tuple[PriorityClass, ...] = (
    PriorityClass.DEFAULT,
    PriorityClass.BACKGROUND,
    PriorityClass.ELEVATED,
)


def _build_policy_submit(
    *,
    model: str,
    prompt: str,
    max_tokens: int,
    stream: bool,
    priority_class: PriorityClass,
    request_index: int,
) -> SubmitRequest:
    rid = uuid4()
    arrival = datetime.now(timezone.utc) - timedelta(milliseconds=request_index * 25)
    return SubmitRequest(
        inference_request=InferenceRequest(
            request_id=rid,
            model=model,
            messages=[Message(role=MessageRole.USER, content=prompt)],
            stream=stream,
            max_tokens=max_tokens,
            priority_class=priority_class,
        ),
        request_context=RequestContext(
            request_id=rid,
            trace_id=f"policy-{rid}",
            span_id="policy",
            arrival_time=arrival,
            model=model,
            stream=stream,
            gateway_instance_id="benchmark",
        ),
    )


def build_policy_submits(scenario: BenchmarkScenario) -> list[SubmitRequest]:
    short = get_profile("short_prompt")
    long_profile = get_profile("long_prompt")
    stream = scenario.stream
    submits: list[SubmitRequest] = []
    for index in range(scenario.request_count):
        profile = short if index % 2 == 0 else long_profile
        priority = _PRIORITY_CYCLE[index % len(_PRIORITY_CYCLE)]
        submits.append(
            _build_policy_submit(
                model="demo",
                prompt=prompt_for_profile(profile),
                max_tokens=profile.max_tokens,
                stream=stream,
                priority_class=priority,
                request_index=index,
            )
        )
    return submits


def _starvation_snapshot(results) -> dict[str, float | int | None]:
    delays = [r.scheduling_delay_ms for r in results if r.scheduling_delay_ms is not None]
    long_delays = [
        r.scheduling_delay_ms
        for r in results
        if r.scheduling_delay_ms is not None and r.max_tokens >= 128
    ]
    queue_waits = [r.queue_wait_ms for r in results if r.queue_wait_ms is not None]
    max_delay = max(delays) if delays else None
    max_long_delay = max(long_delays) if long_delays else None
    max_queue_wait = max(queue_waits) if queue_waits else None
    return {
        "max_scheduling_delay_ms": max_delay,
        "max_long_job_scheduling_delay_ms": max_long_delay,
        "max_queue_wait_ms": max_queue_wait,
        "long_job_count": sum(1 for r in results if r.max_tokens >= 128),
    }


async def run_policy_comparison(
    stack,
    scenario: BenchmarkScenario,
    policy: SchedulerPolicyMode,
    *,
    results_dir=None,
    persist: bool = True,
) -> BenchmarkRun:
    profile = get_profile(scenario.workload_profile)
    hardware = capture_hardware_metadata()
    model_meta = capture_model_metadata(model_id="demo", backend_id="mock", stream=scenario.stream)
    environment = capture_benchmark_environment(model_id="demo", backend_id="mock", stream=scenario.stream)

    gpu_collector = GPUMetricsCollector(
        metrics_recorder=stack.metrics_recorder,
        context_provider=StackRuntimeContext(stack),
    )

    metric_names = (
        f"{PROMETHEUS_PREFIX}_requests_completed_total",
        f"{PROMETHEUS_PREFIX}_scheduler_cycles_total",
        f"{PROMETHEUS_PREFIX}_scheduler_policy_decisions_total",
    )

    started_at = datetime.now(timezone.utc)
    wall_start = time.perf_counter()

    await stack.startup()
    pre_metrics = snapshot_prometheus_metrics(stack.metrics_export(), metric_names)

    submits = build_policy_submits(scenario)
    for submit in submits:
        await stack.orchestrator.lifecycle.process_through_queued(submit)

    results = await _schedule_and_complete_all(stack, submits, profile, gpu_collector)

    duration = time.perf_counter() - wall_start
    post_metrics = snapshot_prometheus_metrics(stack.metrics_export(), metric_names)
    metrics_delta = {k: post_metrics.get(k, 0.0) - pre_metrics.get(k, 0.0) for k in metric_names}

    final_gpu = gpu_collector.collect()
    starvation = _starvation_snapshot(results)
    runtime_snapshot = {
        "kv_cache_occupancy_ratio": final_gpu.kv_cache.cache_occupancy_ratio,
        "active_sequences": final_gpu.kv_cache.active_sequences,
        "gpu_utilization_percent": final_gpu.devices[0].utilization_percent if final_gpu.devices else None,
        "gpu_memory_used_bytes": final_gpu.devices[0].memory_used_bytes if final_gpu.devices else None,
        "gpu_source": final_gpu.devices[0].source.value if final_gpu.devices else None,
        "scheduler_policy_id": policy.policy_id,
        **starvation,
    }

    await stack.shutdown()

    ordered = tuple(sorted(results, key=lambda r: r.request_index))
    summary = build_summary(ordered, duration_seconds=duration)

    batching_mode = CONTINUOUS_BATCHING_MODE
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
        runner="policy_comparison",
        scheduler_policy=policy.policy_id,
        scheduler_policy_config=policy.to_config_dict(),
        batching_mode=batching_mode.mode_id,
        batching_config=batching_mode.to_config_dict(),
        runtime_snapshot=runtime_snapshot,
    )

    if persist:
        persist_run(run, results_dir=results_dir)
    return run
