"""Concurrency scaling report generation. Owner: benchmarks.runner."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from benchmarks.runner.bottleneck import max_sustainable_concurrency
from benchmarks.runner.models import BenchmarkRun

REPORTS_DIR = Path(__file__).resolve().parents[1] / "reports"
DEFAULT_REPORT_PATH = REPORTS_DIR / "concurrency-scaling-analysis.md"


def _fmt(value: float | int | None, *, precision: int = 3) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.{precision}f}"
    return str(value)


def generate_scaling_report(
    runs: list[BenchmarkRun],
    *,
    report_path: Path | None = None,
) -> Path:
    if not runs:
        raise ValueError("no scaling runs supplied")

    path = report_path or DEFAULT_REPORT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(runs, key=lambda r: r.scenario.concurrency)
    env = ordered[0].environment
    sustainable = max_sustainable_concurrency(runs)
    generated_at = datetime.now(timezone.utc).isoformat()

    lines = [
        "# Concurrency Scaling Analysis",
        "",
        f"**Status:** Measured (Session 25)  ",
        f"**Generated:** {generated_at}  ",
        "",
        "Observed measurements only. No optimization recommendations.",
        "",
        "## Methodology",
        "",
        "- Workload: `streaming` profile",
        "- Batching: continuous (`max_batch_size=4`, short admission window)",
        "- Concurrency levels tested: " + ", ".join(str(r.scenario.concurrency) for r in ordered),
        "- All requests enqueued before scheduling; schedule/complete interleaved",
        "- Telemetry sampled before, during, and after request completion",
        "",
        "## Environment",
        "",
    ]

    if env is not None:
        lines.extend(
            [
                f"| Field | Value |",
                f"|-------|-------|",
                f"| OS | {env.os} |",
                f"| Python | {env.python_version} |",
                f"| GPU source | {env.gpu_source} |",
                f"| Model | {env.model_name} |",
                f"| Backend | {env.backend_id} |",
                "",
            ]
        )

    lines.extend(
        [
            "## Throughput and latency",
            "",
            "| Concurrency | requests/s | tokens/s | E2E p50 (ms) | p95 (ms) | p99 (ms) | TTFT p50 (ms) | ITL p50 (ms) | failures |",
            "|-------------|------------|----------|--------------|----------|----------|---------------|--------------|----------|",
        ]
    )
    for run in ordered:
        s = run.summary
        lines.append(
            f"| {run.scenario.concurrency} | "
            f"{_fmt(s.throughput_rps if s else None)} | "
            f"{_fmt(s.tokens_per_second if s else None)} | "
            f"{_fmt(s.latency_ms_p50 if s else None)} | "
            f"{_fmt(s.latency_ms_p95 if s else None)} | "
            f"{_fmt(s.latency_ms_p99 if s else None)} | "
            f"{_fmt(s.ttft_ms_p50 if s else None)} | "
            f"{_fmt(s.itl_ms_p50 if s else None)} | "
            f"{s.failed_requests if s else 'n/a'} |"
        )
    lines.append("")

    lines.extend(
        [
            "## Queue and scheduler",
            "",
            "| Concurrency | peak queue depth | queue_wait p50 (ms) | scheduling_delay p50 (ms) | scheduler cycles | cycle duration avg (ms) |",
            "|-------------|------------------|---------------------|---------------------------|------------------|-------------------------|",
        ]
    )
    for run in ordered:
        rt = run.runtime_snapshot or {}
        s = run.summary
        delays = [r.scheduling_delay_ms for r in run.results if r.scheduling_delay_ms is not None]
        delay_p50 = sorted(delays)[len(delays) // 2] if delays else None
        lines.append(
            f"| {run.scenario.concurrency} | "
            f"{_fmt(rt.get('peak_queue_depth'), precision=0)} | "
            f"{_fmt(s.queue_wait_ms_p50 if s else None)} | "
            f"{_fmt(delay_p50)} | "
            f"{_fmt(rt.get('scheduler_total_cycles'), precision=0)} | "
            f"{_fmt(rt.get('scheduler_cycle_duration_ms_p50'))} |"
        )
    lines.append("")

    lines.extend(
        [
            "## GPU and KV cache",
            "",
            "| Concurrency | peak GPU util % | peak GPU mem (bytes) | peak KV occupancy | peak active sequences | KV pressure events |",
            "|-------------|-----------------|----------------------|-------------------|-----------------------|--------------------|",
        ]
    )
    for run in ordered:
        rt = run.runtime_snapshot or {}
        lines.append(
            f"| {run.scenario.concurrency} | "
            f"{_fmt(rt.get('peak_gpu_utilization_percent'))} | "
            f"{_fmt(rt.get('peak_gpu_memory_used_bytes'), precision=0)} | "
            f"{_fmt(rt.get('peak_kv_cache_occupancy_ratio'))} | "
            f"{_fmt(rt.get('peak_active_sequences'), precision=0)} | "
            f"{_fmt(rt.get('kv_cache_pressure_events'), precision=0)} |"
        )
    lines.append("")

    lines.extend(["## Bottleneck analysis", ""])
    lines.extend(
        [
            "| Concurrency | primary bottleneck | evidence |",
            "|-------------|-------------------|----------|",
        ]
    )
    for run in ordered:
        bn = run.bottleneck
        if bn is None:
            lines.append(f"| {run.scenario.concurrency} | n/a | n/a |")
            continue
        evidence = "; ".join(bn.evidence[:3])
        if len(bn.evidence) > 3:
            evidence += f" (+{len(bn.evidence) - 3} more)"
        lines.append(f"| {run.scenario.concurrency} | `{bn.primary_bottleneck}` | {evidence} |")
    lines.append("")

    lines.extend(
        [
            "## Capacity observations",
            "",
            f"- Max sustainable concurrency (zero failures): {sustainable if sustainable is not None else 'none observed'}",
            "",
        ]
    )

    if sustainable is not None and sustainable < ordered[-1].scenario.concurrency:
        first_fail = next((r for r in ordered if r.summary and r.summary.failed_requests > 0), None)
        if first_fail is not None:
            lines.append(
                f"- First concurrency level with failures: {first_fail.scenario.concurrency} "
                f"({first_fail.summary.failed_requests} failures)"
            )
            lines.append("")

    lines.extend(["## Run identifiers", ""])
    for run in ordered:
        lines.append(f"- concurrency {run.scenario.concurrency}: `{run.run_id}`")
    lines.append("")

    lines.extend(
        [
            "## Limitations",
            "",
            "- Mock backend; not GPU inference capacity",
            "- Bursty admission model",
            "- GPU probe may return fallback zeros",
            "- Bottleneck classification uses configured thresholds on measured signals only",
            "",
        ]
    )

    path.write_text("\n".join(lines))
    return path
