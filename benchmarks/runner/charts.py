"""Reproducible SVG chart generation for batching comparisons. Owner: benchmarks.runner."""

from __future__ import annotations

from pathlib import Path

from benchmarks.runner.models import BenchmarkRun

CHART_DIR = Path(__file__).resolve().parents[1] / "results" / "batching-comparison"

WIDTH = 640
HEIGHT = 400
MARGIN = 60


def _series_key(run: BenchmarkRun) -> tuple[str, int]:
    return (run.batching_mode or "unknown", run.scenario.concurrency)


def _group_runs(runs: list[BenchmarkRun]) -> dict[tuple[str, int], BenchmarkRun]:
    return {_series_key(run): run for run in runs}


def _scale(values: list[float], height: int) -> list[float]:
    if not values:
        return []
    lo = min(values)
    hi = max(values)
    if hi == lo:
        hi = lo + 1.0
    span = height - MARGIN * 2
    return [MARGIN + span - ((v - lo) / (hi - lo)) * span for v in values]


def _render_line_chart(
    *,
    title: str,
    x_labels: list[str],
    series: dict[str, list[float | None]],
    y_label: str,
    output_path: Path,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    colors = {
        "no_batching": "#2563eb",
        "static_batching": "#dc2626",
        "continuous_batching": "#16a34a",
    }

    numeric_series: dict[str, list[float]] = {}
    for name, values in series.items():
        numeric_series[name] = [v if v is not None else 0.0 for v in values]

    all_values = [v for values in numeric_series.values() for v in values]
    y_scaled: dict[str, list[float]] = {
        name: _scale(values, HEIGHT) for name, values in numeric_series.items()
    }

    x_step = (WIDTH - MARGIN * 2) / max(len(x_labels) - 1, 1)
    x_coords = [MARGIN + i * x_step for i in range(len(x_labels))]

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}">',
        f'<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{WIDTH/2}" y="24" text-anchor="middle" font-size="16" font-family="sans-serif">{title}</text>',
        f'<text x="16" y="{HEIGHT/2}" transform="rotate(-90 16 {HEIGHT/2})" text-anchor="middle" font-size="12" font-family="sans-serif">{y_label}</text>',
    ]

    for name, ys in y_scaled.items():
        points = " ".join(f"{x_coords[i]:.1f},{ys[i]:.1f}" for i in range(len(ys)))
        color = colors.get(name, "#444444")
        parts.append(f'<polyline fill="none" stroke="{color}" stroke-width="2" points="{points}"/>')
        parts.append(f'<text x="{WIDTH - MARGIN}" y="{ys[-1]:.1f}" font-size="11" fill="{color}" font-family="sans-serif">{name}</text>')

    for i, label in enumerate(x_labels):
        parts.append(
            f'<text x="{x_coords[i]:.1f}" y="{HEIGHT - 20}" text-anchor="middle" font-size="11" font-family="sans-serif">{label}</text>'
        )

    parts.append("</svg>")
    output_path.write_text("\n".join(parts))
    return output_path


def generate_batching_charts(
    runs: list[BenchmarkRun],
    *,
    output_dir: Path | None = None,
) -> list[Path]:
    directory = output_dir or CHART_DIR
    grouped = _group_runs(runs)
    modes = sorted({key[0] for key in grouped})
    concurrencies = sorted({key[1] for key in grouped})
    x_labels = [str(c) for c in concurrencies]

    throughput_series: dict[str, list[float | None]] = {m: [] for m in modes}
    latency_series: dict[str, list[float | None]] = {m: [] for m in modes}
    gpu_series: dict[str, list[float | None]] = {m: [] for m in modes}

    for concurrency in concurrencies:
        for mode in modes:
            run = grouped.get((mode, concurrency))
            summary = run.summary if run else None
            throughput_series[mode].append(summary.throughput_rps if summary else None)
            latency_series[mode].append(summary.latency_ms_p50 if summary else None)
            gpu_series[mode].append(summary.gpu_utilization_percent_p50 if summary else None)

    paths = [
        _render_line_chart(
            title="Throughput vs Concurrency",
            x_labels=x_labels,
            series=throughput_series,
            y_label="requests/s",
            output_path=directory / "throughput-vs-concurrency.svg",
        ),
        _render_line_chart(
            title="Latency p50 vs Concurrency",
            x_labels=x_labels,
            series=latency_series,
            y_label="latency ms",
            output_path=directory / "latency-vs-concurrency.svg",
        ),
        _render_line_chart(
            title="GPU Utilization p50 vs Concurrency",
            x_labels=x_labels,
            series=gpu_series,
            y_label="gpu util %",
            output_path=directory / "gpu-utilization-vs-concurrency.svg",
        ),
    ]
    return paths
