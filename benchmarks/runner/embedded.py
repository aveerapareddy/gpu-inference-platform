"""Embedded benchmark runner (in-process, mock backend). Owner: benchmarks.runner."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from uuid import uuid4

from common_schemas.inference_request import InferenceRequest, Message, RequestContext, SubmitRequest
from common_schemas.states import MessageRole, RequestState
from gpu_inference_observability.registry.registry import PROMETHEUS_PREFIX
from gpu_inference_observability.streaming.models import StreamSession

from benchmarks.runner.metadata import capture_hardware_metadata, capture_model_metadata
from benchmarks.runner.metrics import build_summary, snapshot_prometheus_metrics
from benchmarks.runner.models import BenchmarkResult, BenchmarkRun, BenchmarkScenario
from benchmarks.runner.profiles import get_profile, prompt_for_profile
from benchmarks.runner.store import persist_run


def _build_submit(*, model: str, prompt: str, max_tokens: int, stream: bool) -> SubmitRequest:
    rid = uuid4()
    return SubmitRequest(
        inference_request=InferenceRequest(
            request_id=rid,
            model=model,
            messages=[Message(role=MessageRole.USER, content=prompt)],
            stream=stream,
            max_tokens=max_tokens,
        ),
        request_context=RequestContext(
            request_id=rid,
            trace_id=f"bench-{rid}",
            span_id="bench",
            arrival_time=datetime.now(timezone.utc),
            model=model,
            stream=stream,
            gateway_instance_id="benchmark",
        ),
    )


def _queue_wait_from_trace(inspector, request_id) -> float | None:
    timeline = inspector.get_request_timeline(request_id)
    if timeline is None:
        return None
    enqueued = None
    dequeued = None
    for event in timeline.events:
        if event.event_type == "request_enqueued":
            enqueued = event.timestamp
        if event.event_type == "request_dequeued":
            dequeued = event.timestamp
    if enqueued is not None and dequeued is not None:
        return (dequeued - enqueued).total_seconds() * 1000.0
    return None


async def _run_sync_request(stack, submit: SubmitRequest, index: int, profile) -> BenchmarkResult:
    started = time.perf_counter()
    try:
        entry = await stack.orchestrator.execute_full_path(submit)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        success = entry.state == RequestState.COMPLETED
        queue_wait = _queue_wait_from_trace(stack.trace_inspector, submit.inference_request.request_id)
        return BenchmarkResult(
            request_index=index,
            request_id=str(submit.inference_request.request_id),
            success=success,
            error=None if success else entry.failure_message,
            latency_ms=elapsed_ms,
            queue_wait_ms=queue_wait,
            scheduler_latency_ms=queue_wait,
            batch_latency_ms=elapsed_ms,
            stream=False,
            prompt_chars=len(prompt_for_profile(profile)),
            max_tokens=profile.max_tokens,
        )
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        return BenchmarkResult(
            request_index=index,
            request_id=str(submit.inference_request.request_id),
            success=False,
            error=str(exc),
            latency_ms=elapsed_ms,
            stream=False,
            prompt_chars=len(prompt_for_profile(profile)),
            max_tokens=profile.max_tokens,
        )


async def _run_stream_request(stack, submit: SubmitRequest, index: int, profile) -> BenchmarkResult:
    from api_gateway.streaming.engine import StreamEngine

    started = time.perf_counter()
    session = StreamSession.create(
        request_id=submit.inference_request.request_id,
        correlation_id=submit.request_context.trace_id,
        model=submit.inference_request.model,
    )
    engine = StreamEngine(stack.stack, stream_events=stack.stack.stream_events)
    chunks = 0
    try:
        await stack.orchestrator.lifecycle.process_through_queued(submit)
        async for _sse in engine.stream_sse(session, submit):
            chunks += 1
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        entry = stack.cp.lifecycle.get_entry(submit.inference_request.request_id)
        success = entry.state == RequestState.COMPLETED
        ttft = session.timing.ttft_ms
        itl = session.timing.inter_token_latencies_ms()
        queue_wait = _queue_wait_from_trace(stack.trace_inspector, submit.inference_request.request_id)
        return BenchmarkResult(
            request_index=index,
            request_id=str(submit.inference_request.request_id),
            success=success,
            latency_ms=elapsed_ms,
            ttft_ms=ttft,
            itl_ms_samples=itl,
            queue_wait_ms=queue_wait,
            scheduler_latency_ms=queue_wait,
            batch_latency_ms=elapsed_ms,
            stream=True,
            prompt_chars=len(prompt_for_profile(profile)),
            max_tokens=profile.max_tokens,
        )
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        return BenchmarkResult(
            request_index=index,
            request_id=str(submit.inference_request.request_id),
            success=False,
            error=str(exc),
            latency_ms=elapsed_ms,
            stream=True,
            prompt_chars=len(prompt_for_profile(profile)),
            max_tokens=profile.max_tokens,
        )


async def _run_one(
    stack,
    scenario: BenchmarkScenario,
    profile,
    index: int,
) -> BenchmarkResult:
    use_stream = scenario.stream
    if scenario.workload_profile == "mixed" and scenario.mixed_stream_ratio is not None:
        use_stream = (index % 2 == 1) if scenario.mixed_stream_ratio >= 0.5 else (index % 2 == 0)
    active_profile = profile
    if use_stream and profile.profile_id != "streaming":
        active_profile = get_profile("streaming")
    prompt = prompt_for_profile(active_profile if not use_stream else get_profile("streaming"))
    submit = _build_submit(
        model="demo",
        prompt=prompt,
        max_tokens=active_profile.max_tokens,
        stream=use_stream,
    )
    if use_stream:
        return await _run_stream_request(stack, submit, index, active_profile)
    return await _run_sync_request(stack, submit, index, active_profile)


async def run_embedded_scenario(
    stack_factory: Callable[[], Awaitable[object] | object],
    scenario: BenchmarkScenario,
    *,
    results_dir=None,
    persist: bool = True,
    metrics_export: Callable[[], str] | None = None,
) -> BenchmarkRun:
    profile = get_profile(scenario.workload_profile)
    hardware = capture_hardware_metadata()
    model_meta = capture_model_metadata(model_id="demo", backend_id="mock", stream=scenario.stream)

    metric_names = (
        f"{PROMETHEUS_PREFIX}_requests_completed_total",
        f"{PROMETHEUS_PREFIX}_requests_failed_total",
        f"{PROMETHEUS_PREFIX}_scheduler_cycles_total",
        f"{PROMETHEUS_PREFIX}_request_ttft_seconds",
    )

    started_at = datetime.now(timezone.utc)
    wall_start = time.perf_counter()

    results: list[BenchmarkResult] = []
    combined_metrics: dict[str, float] = dict.fromkeys(metric_names, 0.0)

    for index in range(scenario.request_count):
        stack = stack_factory()
        if asyncio.iscoroutine(stack):
            stack = await stack
        export_fn = metrics_export or getattr(stack, "metrics_export", None)
        pre_metrics = snapshot_prometheus_metrics(export_fn(), metric_names) if export_fn else {}

        await stack.startup()
        results.append(await _run_one(stack, scenario, profile, index))
        post_metrics = snapshot_prometheus_metrics(export_fn(), metric_names) if export_fn else {}
        for key in metric_names:
            combined_metrics[key] += post_metrics.get(key, 0.0) - pre_metrics.get(key, 0.0)
        await stack.shutdown()

    duration = time.perf_counter() - wall_start
    metrics_delta = combined_metrics

    ordered = tuple(sorted(results, key=lambda r: r.request_index))
    summary = build_summary(ordered, duration_seconds=duration)

    run = BenchmarkRun(
        scenario=scenario,
        hardware=hardware,
        model=model_meta,
        started_at=started_at,
        completed_at=datetime.now(timezone.utc),
        results=ordered,
        summary=summary,
        metrics_snapshot=metrics_delta,
        runner="embedded",
    )

    if persist:
        persist_run(run, results_dir=results_dir)
    return run
