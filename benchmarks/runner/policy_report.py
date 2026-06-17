"""Scheduler policy comparison report. Owner: benchmarks.runner."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from benchmarks.runner.models import BenchmarkRun
from benchmarks.runner.profiles import PROFILES
from benchmarks.runner.scheduler_policies import SCHEDULER_POLICIES

REPORTS_DIR = Path(__file__).resolve().parents[1] / "reports"
DEFAULT_REPORT_PATH = REPORTS_DIR / "scheduler-policy-analysis.md"

POLICY_COMPARISON_SCENARIOS: tuple[str, ...] = (
    "scheduler_policy_c4",
    "scheduler_policy_c8",
)


def _fmt(value: float | int | None, *, precision: int = 3) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.{precision}f}"
    return str(value)


def _concurrency(run: BenchmarkRun) -> int:
    return run.scenario.concurrency


def _scheduling_delays(run: BenchmarkRun) -> list[float]:
    return [
        r.scheduling_delay_ms
        for r in run.results
        if r.scheduling_delay_ms is not None
    ]


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = int(round((pct / 100.0) * (len(ordered) - 1)))
    return ordered[max(0, min(index, len(ordered) - 1))]


def generate_policy_analysis_report(
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
    profile = PROFILES.get("mixed_job_sizes", PROFILES["streaming"])

    lines = [
        "# Scheduler Policy Analysis",
        "",
        f"**Status:** Measured (Session 26)  ",
        f"**Generated:** {generated_at}  ",
        "",
        "Observed measurements only. Policy ordering changed; batching and backend held constant.",
        "",
        "## Methodology",
        "",
        "Fixed runtime configuration across all policies:",
        "",
        "| Parameter | Value |",
        "|-----------|-------|",
        "| batching | continuous (`max_batch_size=4`, `admission_window_ms=50`) |",
        "| backend | mock |",
        "| model | demo |",
        "| workload | alternating short (`max_tokens=32`) and long (`max_tokens=256`) |",
        "| priority | cycles DEFAULT / BACKGROUND / ELEVATED per request index |",
        "",
        "Policies compared:",
        "",
        "| Policy | Selection rule |",
        "|--------|----------------|",
    ]
    for policy in SCHEDULER_POLICIES.values():
        lines.append(f"| `{policy.policy_id}` | {policy.description} |")

    lines.extend(
        [
            "",
            "Execution flow:",
            "",
            "1. Enqueue all requests before scheduling",
            "2. Interleave scheduler cycles and request completion",
            "3. Collect per-request latency, TTFT, ITL, queue wait, scheduling delay",
            "",
            f"Concurrency levels: 4, 8. Profile id: `{profile.profile_id}`.",
            "",
            "## Environment",
            "",
        ]
    )

    if env is not None:
        lines.extend(
            [
                "| Field | Value |",
                "|-------|-------|",
                f"| OS | {env.os} |",
                f"| Python | {env.python_version} |",
                f"| vLLM | {env.vllm_version or 'not installed'} |",
                f"| GPU source | {env.gpu_source} |",
                f"| Model | {env.model_name} |",
                f"| Backend | {env.backend_id} |",
                "",
            ]
        )

    lines.extend(["## Throughput", ""])
    lines.extend(
        [
            "| Policy | Concurrency | requests/s | tokens/s | failures |",
            "|--------|-------------|------------|----------|----------|",
        ]
    )
    for run in sorted(runs, key=lambda r: (r.scheduler_policy or "", _concurrency(r))):
        summary = run.summary
        failures = summary.failed_requests if summary else 0
        lines.append(
            f"| `{run.scheduler_policy}` | {_concurrency(run)} | "
            f"{_fmt(summary.throughput_rps if summary else None)} | "
            f"{_fmt(summary.tokens_per_second if summary else None)} | {failures} |"
        )
    lines.append("")

    lines.extend(["## Latency (ms)", ""])
    lines.extend(
        [
            "| Policy | Concurrency | E2E p50 | p95 | p99 | TTFT p50 | ITL p50 | queue_wait p50 |",
            "|--------|-------------|---------|-----|-----|----------|---------|----------------|",
        ]
    )
    for run in sorted(runs, key=lambda r: (r.scheduler_policy or "", _concurrency(r))):
        summary = run.summary
        lines.append(
            f"| `{run.scheduler_policy}` | {_concurrency(run)} | "
            f"{_fmt(summary.latency_ms_p50 if summary else None)} | "
            f"{_fmt(summary.latency_ms_p95 if summary else None)} | "
            f"{_fmt(summary.latency_ms_p99 if summary else None)} | "
            f"{_fmt(summary.ttft_ms_p50 if summary else None)} | "
            f"{_fmt(summary.itl_ms_p50 if summary else None)} | "
            f"{_fmt(summary.queue_wait_ms_p50 if summary else None)} |"
        )
    lines.append("")

    lines.extend(["## Scheduling delay and starvation indicators", ""])
    lines.extend(
        [
            "| Policy | Concurrency | sched_delay p50 | p95 | max | max long-job delay | max queue wait |",
            "|--------|-------------|-----------------|-----|-----|--------------------|----------------|",
        ]
    )
    for run in sorted(runs, key=lambda r: (r.scheduler_policy or "", _concurrency(r))):
        delays = _scheduling_delays(run)
        snapshot = run.runtime_snapshot
        lines.append(
            f"| `{run.scheduler_policy}` | {_concurrency(run)} | "
            f"{_fmt(_percentile(delays, 50.0))} | "
            f"{_fmt(_percentile(delays, 95.0))} | "
            f"{_fmt(max(delays) if delays else None)} | "
            f"{_fmt(snapshot.get('max_long_job_scheduling_delay_ms'))} | "
            f"{_fmt(snapshot.get('max_queue_wait_ms'))} |"
        )
    lines.append("")

    lines.extend(["## Observed tradeoffs", ""])
    best_throughput = max(
        runs,
        key=lambda r: (r.summary.throughput_rps or 0.0) if r.summary else 0.0,
    )
    best_latency = min(
        runs,
        key=lambda r: (r.summary.latency_ms_p50 or float("inf")) if r.summary else float("inf"),
    )
    lowest_long_delay = min(
        runs,
        key=lambda r: r.runtime_snapshot.get("max_long_job_scheduling_delay_ms") or float("inf"),
    )
    lines.extend(
        [
            f"- Highest throughput observed: `{best_throughput.scheduler_policy}` at concurrency "
            f"{_concurrency(best_throughput)} "
            f"({ _fmt(best_throughput.summary.throughput_rps if best_throughput.summary else None)} requests/s).",
            f"- Lowest E2E p50 latency observed: `{best_latency.scheduler_policy}` at concurrency "
            f"{_concurrency(best_latency)} "
            f"({_fmt(best_latency.summary.latency_ms_p50 if best_latency.summary else None)} ms).",
            f"- Lowest max long-job scheduling delay observed: `{lowest_long_delay.scheduler_policy}` at concurrency "
            f"{_concurrency(lowest_long_delay)} "
            f"({_fmt(lowest_long_delay.runtime_snapshot.get('max_long_job_scheduling_delay_ms'))} ms).",
            "",
            "## Limitations",
            "",
            "- Measurements use mock backend; job-size heuristics do not change mock execution time",
            "- All requests enqueued before scheduling; queue_wait spread is limited",
            "- Fairness policy state resets per benchmark stack instance",
            "- No vLLM or GPU-backed policy runs in this session",
            "- Tradeoff bullets are descriptive comparisons of measured runs, not causal claims",
            "",
        ]
    )

    path.write_text("\n".join(lines))
    return path
