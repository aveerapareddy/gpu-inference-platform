"""Scaling chart generation. Owner: benchmarks.runner."""

from __future__ import annotations

from pathlib import Path

from benchmarks.runner.charts import _render_line_chart
from benchmarks.runner.models import BenchmarkRun

CHART_DIR = Path(__file__).resolve().parents[1] / "results" / "scaling-analysis"


def _single_series(runs: list[BenchmarkRun], extractor) -> dict[str, list[float | None]]:
    ordered = sorted(runs, key=lambda r: r.scenario.concurrency)
    return {"measured": [extractor(r) for r in ordered]}


def generate_scaling_charts(
    runs: list[BenchmarkRun],
    *,
    output_dir: Path | None = None,
) -> list[Path]:
    directory = output_dir or CHART_DIR
    directory.mkdir(parents=True, exist_ok=True)
    ordered = sorted(runs, key=lambda r: r.scenario.concurrency)
    x_labels = [str(r.scenario.concurrency) for r in ordered]

    def _summary_val(run: BenchmarkRun, attr: str):
        summary = run.summary
        return getattr(summary, attr, None) if summary else None

    def _runtime_peak(run: BenchmarkRun, key: str):
        return (run.runtime_snapshot or {}).get(key)

    return [
        _render_line_chart(
            title="Throughput vs Concurrency",
            x_labels=x_labels,
            series=_single_series(runs, lambda r: _summary_val(r, "throughput_rps")),
            y_label="requests/s",
            output_path=directory / "throughput-vs-concurrency.svg",
        ),
        _render_line_chart(
            title="TTFT p50 vs Concurrency",
            x_labels=x_labels,
            series=_single_series(runs, lambda r: _summary_val(r, "ttft_ms_p50")),
            y_label="TTFT ms",
            output_path=directory / "ttft-vs-concurrency.svg",
        ),
        _render_line_chart(
            title="Latency p95 vs Concurrency",
            x_labels=x_labels,
            series=_single_series(runs, lambda r: _summary_val(r, "latency_ms_p95")),
            y_label="latency p95 ms",
            output_path=directory / "latency-p95-vs-concurrency.svg",
        ),
        _render_line_chart(
            title="Queue Depth Peak vs Concurrency",
            x_labels=x_labels,
            series=_single_series(runs, lambda r: _runtime_peak(r, "peak_queue_depth")),
            y_label="peak queue depth",
            output_path=directory / "queue-depth-vs-concurrency.svg",
        ),
        _render_line_chart(
            title="GPU Memory Peak vs Concurrency",
            x_labels=x_labels,
            series=_single_series(
                runs,
                lambda r: float(_runtime_peak(r, "peak_gpu_memory_used_bytes") or 0),
            ),
            y_label="bytes",
            output_path=directory / "gpu-memory-vs-concurrency.svg",
        ),
        _render_line_chart(
            title="KV Cache Occupancy Peak vs Concurrency",
            x_labels=x_labels,
            series=_single_series(runs, lambda r: _runtime_peak(r, "peak_kv_cache_occupancy_ratio")),
            y_label="occupancy ratio",
            output_path=directory / "kv-cache-vs-concurrency.svg",
        ),
    ]
