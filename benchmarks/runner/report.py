"""Baseline report generation. Owner: benchmarks.runner."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from benchmarks.runner.models import BenchmarkRun
from benchmarks.runner.profiles import PROFILES, estimated_input_tokens_for_profile

REPORTS_DIR = Path(__file__).resolve().parents[1] / "reports"
DEFAULT_REPORT_PATH = REPORTS_DIR / "baseline-results.md"


def _fmt(value: float | int | None, *, suffix: str = "", precision: int = 3) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.{precision}f}{suffix}"
    return f"{value}{suffix}"


def _fmt_bytes(value: int | None) -> str:
    if value is None:
        return "n/a"
    if value >= 1_073_741_824:
        return f"{value / 1_073_741_824:.2f} GiB"
    if value >= 1_048_576:
        return f"{value / 1_048_576:.2f} MiB"
    return f"{value} B"


def generate_baseline_report(
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

    lines: list[str] = [
        "# Baseline Performance Results",
        "",
        f"**Status:** Measured (Session 23)  ",
        f"**Generated:** {generated_at}  ",
        f"**Runner:** {runs[0].runner}  ",
        "",
        "This report records collected measurements only. No tuning was applied.",
        "",
        "## Methodology",
        "",
        "- Embedded ValidationStack with mock backend (`demo` model)",
        "- One stack instance per request; requests within a scenario run sequentially",
        "- Latency measured as wall-clock time per request",
        "- TTFT and ITL measured on streaming requests from `StreamSession` timing",
        "- GPU metrics sampled via `GPUMetricsCollector` after each request",
        "- Input token counts are estimated (`chars/4`); output token counts are measured when backend reports them",
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
                f"| Platform | {env.platform} |",
                f"| Python | {env.python_version} |",
                f"| vLLM | {env.vllm_version or 'not installed'} |",
                f"| CPU | {env.cpu_model or 'n/a'} |",
                f"| RAM | {_fmt_bytes(env.ram_bytes)} |",
                f"| GPU | {env.gpu_model or 'n/a'} |",
                f"| GPU memory | {_fmt_bytes(env.gpu_memory_total_bytes)} |",
                f"| GPU source | {env.gpu_source} |",
                f"| Model | {env.model_name} |",
                f"| Model size | {env.model_size or 'n/a'} |",
                f"| Backend | {env.backend_id} |",
                f"| Hostname | {env.hostname or 'n/a'} |",
                "",
            ]
        )
    else:
        lines.append("Environment metadata missing from run records.")
        lines.append("")

    lines.extend(
        [
            "## Reference workloads",
            "",
            "| Profile | Est. input tokens | Target output tokens | Stream | Rationale |",
            "|---------|-------------------|----------------------|--------|-----------|",
        ]
    )
    for profile_id in ("short_prompt", "medium_prompt", "long_prompt", "streaming"):
        profile = PROFILES[profile_id]
        est = estimated_input_tokens_for_profile(profile)
        lines.append(
            f"| `{profile_id}` | {est} (estimated) | {profile.target_output_tokens} | "
            f"{'yes' if profile.stream else 'no'} | {profile.rationale} |"
        )
    lines.append("")

    lines.extend(["## Single-request baseline (concurrency = 1)", ""])
    single_runs = [r for r in runs if r.scenario.concurrency == 1]
    if single_runs:
        lines.extend(
            [
                "| Scenario | Latency (ms) | TTFT (ms) | ITL p50 (ms) | Tokens out | GPU util % | GPU mem used |",
                "|----------|--------------|-----------|--------------|------------|------------|--------------|",
            ]
        )
        for run in single_runs:
            result = run.results[0] if run.results else None
            summary = run.summary
            lines.append(
                "| "
                + " | ".join(
                    [
                        run.scenario.scenario_id,
                        _fmt(result.latency_ms if result else None),
                        _fmt(result.ttft_ms if result else None),
                        _fmt(summary.itl_ms_p50 if summary else None),
                        _fmt(result.tokens_generated if result else None, precision=0),
                        _fmt(result.gpu_utilization_percent if result else None),
                        _fmt_bytes(result.gpu_memory_used_bytes if result else None),
                    ]
                )
                + " |"
            )
        lines.append("")

    lines.extend(["## Low-concurrency measurements", ""])
    conc_runs = [r for r in runs if r.scenario.concurrency > 1]
    if conc_runs:
        lines.extend(
            [
                "| Scenario | Concurrency | Throughput (rps) | Latency p50 (ms) | p95 (ms) | p99 (ms) | TTFT p50 (ms) | TTFT p95 (ms) | GPU util p50 % |",
                "|----------|-------------|------------------|------------------|----------|----------|---------------|---------------|----------------|",
            ]
        )
        for run in conc_runs:
            summary = run.summary
            if summary is None:
                continue
            lines.append(
                "| "
                + " | ".join(
                    [
                        run.scenario.scenario_id,
                        str(run.scenario.concurrency),
                        _fmt(summary.throughput_rps),
                        _fmt(summary.latency_ms_p50),
                        _fmt(summary.latency_ms_p95),
                        _fmt(summary.latency_ms_p99),
                        _fmt(summary.ttft_ms_p50),
                        _fmt(summary.ttft_ms_p95),
                        _fmt(summary.gpu_utilization_percent_p50),
                    ]
                )
                + " |"
            )
        lines.append("")

    lines.extend(
        [
            "## Run identifiers",
            "",
        ]
    )
    for run in runs:
        lines.append(f"- `{run.scenario.scenario_id}`: `{run.run_id}`")
    lines.append("")

    lines.extend(
        [
            "## Limitations",
            "",
            "- Measurements use mock backend unless operator configures vLLM backend separately",
            "- Embedded runner does not execute concurrent requests in-process; concurrency scenarios measure sequential request latency aggregates",
            "- GPU metrics reflect host probe state (`nvml`, `fallback_unavailable`, or `simulated`) at sample time",
            "- No comparison or regression analysis in Session 23",
            "",
        ]
    )

    path.write_text("\n".join(lines))
    return path
