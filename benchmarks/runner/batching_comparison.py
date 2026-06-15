"""Batching strategy comparison runner. Owner: benchmarks.runner."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from uuid import UUID

from common_schemas.inference_request import SubmitRequest
from common_schemas.states import RequestState
from gpu_inference_observability.gpu.collector import GPUMetricsCollector
from gpu_inference_observability.registry.registry import PROMETHEUS_PREFIX
from gpu_inference_observability.streaming.models import StreamSession

from benchmarks.runner.batching_modes import BatchingMode
from benchmarks.runner.context import StackRuntimeContext
from benchmarks.runner.embedded import (
    _apply_gpu_metrics,
    _build_submit,
    _queue_wait_from_trace,
    _result_base_fields,
    _tokens_from_entry,
)
from benchmarks.runner.metadata import capture_benchmark_environment, capture_hardware_metadata, capture_model_metadata
from benchmarks.runner.metrics import build_summary, snapshot_prometheus_metrics
from benchmarks.runner.models import BenchmarkResult, BenchmarkRun, BenchmarkScenario
from benchmarks.runner.profiles import get_profile, prompt_for_profile
from benchmarks.runner.store import persist_run
from inference_adapter.streaming.bridge import stream_inference_request

BATCHING_COMPARISON_SCENARIOS: tuple[str, ...] = (
    "batching_comparison_c2",
    "batching_comparison_c4",
    "batching_comparison_c8",
)


def _scheduling_delay_from_trace(inspector, request_id) -> float | None:
    timeline = inspector.get_request_timeline(request_id)
    if timeline is None:
        return None
    enqueued = None
    scheduled = None
    for event in timeline.events:
        if event.event_type == "request_enqueued":
            enqueued = event.timestamp
        if event.event_type == "request_scheduled":
            scheduled = event.timestamp
    if enqueued is not None and scheduled is not None:
        return (scheduled - enqueued).total_seconds() * 1000.0
    return None


def _find_batch_for_request(stack, request_id: UUID):
    for batch in stack.scheduler.batch.list_batches():
        for member in batch.members:
            if member.request_id == request_id:
                return batch
    return None


def _request_age_ms(stack, request_id: UUID) -> float | None:
    try:
        entry = stack.cp.lifecycle.get_entry(request_id)
    except Exception:
        return None
    return (datetime.now(timezone.utc) - entry.created_at).total_seconds() * 1000.0


async def _transition_and_stream(
    stack,
    submit: SubmitRequest,
    index: int,
    profile,
    gpu_collector: GPUMetricsCollector | None,
    *,
    batch_members_at_dispatch: int | None = None,
) -> BenchmarkResult:
    request_id = submit.inference_request.request_id
    base = _result_base_fields(profile, stream=True)
    queue_depth = stack.cp.queue.depth()
    request_age = _request_age_ms(stack, request_id)
    scheduling_delay = _scheduling_delay_from_trace(stack.trace_inspector, request_id)

    batch = _find_batch_for_request(stack, request_id)
    batch_members = batch_members_at_dispatch
    if batch_members is None and batch is not None:
        batch_members = batch.active_member_count
    backend_id = stack.scheduler.settings.default_backend_id

    started = time.perf_counter()
    session = StreamSession.create(
        request_id=request_id,
        correlation_id=submit.request_context.trace_id,
        model=submit.inference_request.model,
    )
    try:
        entry = stack.cp.lifecycle.get_entry(request_id)
        if entry.state == RequestState.QUEUED:
            if batch is None:
                raise RuntimeError("request_not_placed_in_batch")
            stack.cp.lifecycle.transition(request_id, RequestState.SCHEDULED, batch_id=batch.batch_id)
            stack.cp.lifecycle.transition(request_id, RequestState.BATCHED)
            stack.cp.lifecycle.transition(request_id, RequestState.SUBMITTED, backend_id=backend_id)
        elif entry.state == RequestState.BATCHED:
            stack.cp.lifecycle.transition(request_id, RequestState.SUBMITTED, backend_id=backend_id)
        elif entry.state not in {RequestState.SUBMITTED, RequestState.STREAMING, RequestState.COMPLETED}:
            raise RuntimeError(f"unexpected_state:{entry.state.value}")

        entry = stack.cp.lifecycle.get_entry(request_id)
        if entry.state == RequestState.SUBMITTED:
            stack.cp.lifecycle.transition(request_id, RequestState.STREAMING)

        registered = stack.adapter.get_backend(backend_id)
        if registered is None:
            raise RuntimeError(f"backend_not_found:{backend_id}")

        ttft_ms: float | None = None
        itl_samples: list[float] = []
        last_token_at = time.perf_counter()
        token_count = 0

        async for _chunk in stream_inference_request(
            registered.backend,
            request_id=request_id,
            stream_id=session.stream_id,
            inference_request=submit.inference_request,
            model=submit.inference_request.model,
            batch_id=batch.batch_id if batch is not None else None,
        ):
            now = time.perf_counter()
            token_count += 1
            if ttft_ms is None:
                ttft_ms = (now - started) * 1000.0
            else:
                itl_samples.append((now - last_token_at) * 1000.0)
            last_token_at = now

        stack.scheduler.batch.complete_request(request_id)
        stack.cp.lifecycle.complete_request(request_id)
        elapsed_ms = (time.perf_counter() - started) * 1000.0

        entry = stack.cp.lifecycle.get_entry(request_id)
        success = entry.state == RequestState.COMPLETED
        ttft = ttft_ms
        itl = tuple(itl_samples)
        queue_wait = _queue_wait_from_trace(stack.trace_inspector, request_id)
        tokens = _tokens_from_entry(entry)
        if tokens is None and token_count:
            tokens = token_count

        result = BenchmarkResult(
            request_index=index,
            request_id=str(request_id),
            success=success,
            latency_ms=elapsed_ms,
            ttft_ms=ttft,
            itl_ms_samples=itl,
            queue_wait_ms=queue_wait,
            scheduler_latency_ms=scheduling_delay,
            batch_latency_ms=elapsed_ms,
            queue_depth_at_schedule=queue_depth,
            request_age_ms=request_age,
            scheduling_delay_ms=scheduling_delay,
            batch_member_count_at_dispatch=batch_members,
            tokens_generated=tokens,
            **base,
        )
        if gpu_collector is not None:
            snapshot = gpu_collector.collect()
            result = _apply_gpu_metrics(result, snapshot)
            result = result.model_copy(
                update={
                    "kv_cache_occupancy_ratio": snapshot.kv_cache.cache_occupancy_ratio,
                    "active_sequences": snapshot.kv_cache.active_sequences,
                }
            )
        return result
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        return BenchmarkResult(
            request_index=index,
            request_id=str(request_id),
            success=False,
            error=str(exc),
            latency_ms=elapsed_ms,
            queue_depth_at_schedule=queue_depth,
            request_age_ms=request_age,
            scheduling_delay_ms=scheduling_delay,
            batch_member_count_at_dispatch=batch_members,
            **base,
        )


async def _schedule_queued_requests(stack, *, max_cycles: int) -> None:
    for _ in range(max_cycles):
        queued = stack.cp.registry.list_by_state(RequestState.QUEUED)
        if not queued:
            return
        await stack.scheduler.run_scheduling_cycle()


def _is_placed_in_batch(stack, request_id: UUID) -> bool:
    return _find_batch_for_request(stack, request_id) is not None


async def _schedule_and_complete_all(
    stack,
    submits: list[SubmitRequest],
    profile,
    gpu_collector: GPUMetricsCollector | None,
    *,
    on_request_complete=None,
) -> list[BenchmarkResult]:
    results_by_index: dict[int, BenchmarkResult] = {}
    dispatch_sizes: dict[int, int] = {}
    pending = list(enumerate(submits))
    max_rounds = len(submits) * 4

    for _round in range(max_rounds):
        if not pending:
            break
        await _schedule_queued_requests(stack, max_cycles=1)

        for index, submit in pending:
            request_id = submit.inference_request.request_id
            if index not in dispatch_sizes and _is_placed_in_batch(stack, request_id):
                batch = _find_batch_for_request(stack, request_id)
                if batch is not None:
                    dispatch_sizes[index] = batch.active_member_count

        still_pending: list[tuple[int, SubmitRequest]] = []
        for index, submit in pending:
            request_id = submit.inference_request.request_id
            entry = stack.cp.lifecycle.get_entry(request_id)
            if entry.state == RequestState.COMPLETED:
                continue
            if not _is_placed_in_batch(stack, request_id):
                still_pending.append((index, submit))
                continue
            result = await _transition_and_stream(
                stack,
                submit,
                index,
                profile,
                gpu_collector,
                batch_members_at_dispatch=dispatch_sizes.get(index),
            )
            results_by_index[index] = result
            if on_request_complete is not None:
                on_request_complete(result)

        pending = still_pending

    for index, submit in pending:
        base = _result_base_fields(profile, stream=True)
        results_by_index[index] = BenchmarkResult(
            request_index=index,
            request_id=str(submit.inference_request.request_id),
            success=False,
            error="request_not_placed_in_batch",
            **base,
        )

    return [results_by_index[i] for i in range(len(submits))]


async def run_batching_comparison(
    stack,
    scenario: BenchmarkScenario,
    mode: BatchingMode,
    *,
    results_dir=None,
    persist: bool = True,
) -> BenchmarkRun:
    profile = get_profile(scenario.workload_profile)
    prompt = prompt_for_profile(profile)
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
    )

    started_at = datetime.now(timezone.utc)
    wall_start = time.perf_counter()

    await stack.startup()
    pre_metrics = snapshot_prometheus_metrics(stack.metrics_export(), metric_names)

    submits = [
        _build_submit(
            model="demo",
            prompt=prompt,
            max_tokens=profile.max_tokens,
            stream=True,
        )
        for _ in range(scenario.request_count)
    ]

    for submit in submits:
        await stack.orchestrator.lifecycle.process_through_queued(submit)

    results = await _schedule_and_complete_all(stack, submits, profile, gpu_collector)

    duration = time.perf_counter() - wall_start
    post_metrics = snapshot_prometheus_metrics(stack.metrics_export(), metric_names)
    metrics_delta = {k: post_metrics.get(k, 0.0) - pre_metrics.get(k, 0.0) for k in metric_names}

    final_gpu = gpu_collector.collect()
    runtime_snapshot = {
        "kv_cache_occupancy_ratio": final_gpu.kv_cache.cache_occupancy_ratio,
        "active_sequences": final_gpu.kv_cache.active_sequences,
        "gpu_utilization_percent": final_gpu.devices[0].utilization_percent if final_gpu.devices else None,
        "gpu_memory_used_bytes": final_gpu.devices[0].memory_used_bytes if final_gpu.devices else None,
        "gpu_source": final_gpu.devices[0].source.value if final_gpu.devices else None,
    }

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
        runner="batching_comparison",
        batching_mode=mode.mode_id,
        batching_config=mode.to_config_dict(),
        runtime_snapshot=runtime_snapshot,
    )

    if persist:
        persist_run(run, results_dir=results_dir)
    return run
