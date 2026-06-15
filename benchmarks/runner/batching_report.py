"""Batching comparison report generation. Owner: benchmarks.runner."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from benchmarks.runner.batching_modes import BATCHING_MODES
from benchmarks.runner.models import BenchmarkRun
from benchmarks.runner.profiles import PROFILES, estimated_input_tokens_for_profile

REPORTS_DIR = Path(__file__).resolve().parents[1] / "reports"
DEFAULT_REPORT_PATH = REPORTS_DIR / "continuous-batching-analysis.md"


def _fmt(value: float | int | None, *, precision: int = 3) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.{precision}f}"
    return str(value)


def _concurrency(run: BenchmarkRun) -> int:
    return run.scenario.concurrency


def generate_batching_analysis_report(
    runs: list[BenchmarkRun],
    *,
    report_path: Path | None = None,
) -> Path:
    if not runs:
        raise ValueError("no benchmark runs supplied")

    path = report_path or DEFAULT_REPORT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    env = runs[0].environment
    generated_at = datetime.now(timezone.utc).isoformat()
    profile = PROFILES["streaming"]

    lines = [
        "# Continuous Batching Analysis",
        "",
        f"**Status:** Measured (Session 24)  ",
        f"**Generated:** {generated_at}  ",
        "",
        "Observed measurements only. No tuning applied. No causal claims.",
        "",
        "## Methodology",
        "",
        "Compare three scheduler configurations on identical streaming workloads:",
        "",
        "| Mode | max_batch_size | admission_window_ms | min_dispatch_members |",
        "|------|----------------|---------------------|----------------------|",
    ]
    for mode in BATCHING_MODES.values():
        lines.append(
            f"| `{mode.mode_id}` | {mode.max_batch_size} | {mode.batch_admission_window_ms} | "
            f"{mode.min_dispatch_members} |"
        )

    lines.extend(
        [
            "",
            "Execution flow:",
            "",
            "1. Enqueue all requests before scheduling",
            "2. Run scheduler cycles until queue empty",
            "3. Complete streaming requests and collect per-request metrics",
            "",
            "Concurrency levels: 2, 4, 8. Workload: `streaming` profile.",
            "",
            f"Estimated input tokens per request: {estimated_input_tokens_for_profile(profile)} (chars/4 estimate).",
            f"Target output tokens: {profile.target_output_tokens}.",
            "",
            "## Environment",
            "",
        ]
    )

    if env is not None:
        lines.extend(
            [
                f"| Field | Value |",
                f"|-------|-------|",
                f"| OS | {env.os} |",
                f"| Python | {env.python_version} |",
                f"| vLLM | {env.vllm_version or 'not installed'} |",
                f"| GPU source | {env.gpu_source} |",
                f"| Model | {env.model_name} |",
                f"| Backend | {env.backend_id} |",
                "",
            ]
        )

    lines.extend(["## Throughput measurements", ""])
    lines.extend(
        [
            "| Mode | Concurrency | requests/s p50 | tokens/s |",
            "|------|-------------|----------------|----------|",
        ]
    )
    for run in sorted(runs, key=lambda r: (r.batching_mode or "", _concurrency(r))):
        summary = run.summary
        lines.append(
            f"| `{run.batching_mode}` | {_concurrency(run)} | "
            f"{_fmt(summary.throughput_rps if summary else None)} | "
            f"{_fmt(summary.tokens_per_second if summary else None)} |"
        )
    lines.append("")

    lines.extend(["## Latency measurements (ms)", ""])
    lines.extend(
        [
            "| Mode | Concurrency | E2E p50 | p95 | p99 | TTFT p50 | p95 | p99 | ITL p50 | p95 |",
            "|------|-------------|---------|-----|-----|----------|-----|-----|---------|-----|",
        ]
    )
    for run in sorted(runs, key=lambda r: (r.batching_mode or "", _concurrency(r))):
        s = run.summary
        if s is None:
            continue
        lines.append(
            f"| `{run.batching_mode}` | {_concurrency(run)} | "
            f"{_fmt(s.latency_ms_p50)} | {_fmt(s.latency_ms_p95)} | {_fmt(s.latency_ms_p99)} | "
            f"{_fmt(s.ttft_ms_p50)} | {_fmt(s.ttft_ms_p95)} | {_fmt(s.ttft_ms_p99)} | "
            f"{_fmt(s.itl_ms_p50)} | {_fmt(s.itl_ms_p95)} |"
        )
    lines.append("")

    lines.extend(["## Queue impact", ""])
    lines.extend(
        [
            "| Mode | Concurrency | queue_wait p50 (ms) | scheduling_delay p50 (ms) | request_age p50 (ms) | queue_depth at schedule |",
            "|------|-------------|---------------------|---------------------------|----------------------|-------------------------|",
        ]
    )
    for run in sorted(runs, key=lambda r: (r.batching_mode or "", _concurrency(r))):
        waits = [r.queue_wait_ms for r in run.results if r.queue_wait_ms is not None]
        delays = [r.scheduling_delay_ms for r in run.results if r.scheduling_delay_ms is not None]
        ages = [r.request_age_ms for r in run.results if r.request_age_ms is not None]
        depths = [r.queue_depth_at_schedule for r in run.results if r.queue_depth_at_schedule is not None]

        def p50(values: list[float]) -> float | None:
            if not values:
                return None
            ordered = sorted(values)
            return ordered[len(ordered) // 2]

        lines.append(
            f"| `{run.batching_mode}` | {_concurrency(run)} | "
            f"{_fmt(p50(waits))} | {_fmt(p50(delays))} | {_fmt(p50(ages))} | "
            f"{_fmt(p50([float(v) for v in depths]) if depths else None, precision=0)} |"
        )
    lines.append("")

    lines.extend(["## GPU utilization comparison", ""])
    lines.extend(
        [
            "| Mode | Concurrency | GPU util p50 % | GPU mem p50 (bytes) | KV occupancy p50 | active sequences p50 |",
            "|------|-------------|----------------|---------------------|------------------|----------------------|",
        ]
    )
    for run in sorted(runs, key=lambda r: (r.batching_mode or "", _concurrency(r))):
        s = run.summary
        lines.append(
            f"| `{run.batching_mode}` | {_concurrency(run)} | "
            f"{_fmt(s.gpu_utilization_percent_p50 if s else None)} | "
            f"{_fmt(s.gpu_memory_used_bytes_p50 if s else None, precision=0)} | "
            f"{_fmt(s.kv_cache_occupancy_ratio_p50 if s else None)} | "
            f"{_fmt(s.active_sequences_p50 if s else None, precision=0)} |"
        )
    lines.append("")

    lines.extend(["## Batch dispatch observations", ""])
    lines.extend(
        [
            "| Mode | Concurrency | batch members at dispatch (per request) |",
            "|------|-------------|----------------------------------------|",
        ]
    )
    for run in sorted(runs, key=lambda r: (r.batching_mode or "", _concurrency(r))):
        members = [r.batch_member_count_at_dispatch for r in run.results if r.batch_member_count_at_dispatch]
        observed = ", ".join(str(m) for m in members) if members else "n/a"
        lines.append(f"| `{run.batching_mode}` | {_concurrency(run)} | {observed} |")
    lines.append("")

    lines.extend(["## Run identifiers", ""])
    for run in runs:
        lines.append(
            f"- `{run.batching_mode}` / `{run.scenario.scenario_id}`: `{run.run_id}`"
        )
    lines.append("")

    lines.extend(
        [
            "## Limitations",
            "",
            "- Mock backend; measurements reflect scheduler and platform path behavior",
            "- All requests enqueued before first scheduling cycle; not a staggered arrival model",
            "- Static mode requires min_dispatch_members instrumentation on BatchDispatchService",
            "- GPU metrics depend on host probe availability",
            "- No universal throughput or latency conclusions drawn in this report",
            "",
        ]
    )

    path.write_text("\n".join(lines))
    return path
