# observability

Status: Implemented (Session 3 — scaffolding)
Implementation: Logging/tracing/metric names; no Prometheus or OpenTelemetry

Python package `gpu_inference_observability` (distribution: `gpu-inference-observability`).

## Install

```bash
pip install -e packages/observability
```

## Modules

| Module | Purpose |
| --- | --- |
| `logging.py` | `LogContext`, `StructuredLogger` (JSON lines to stderr) |
| `tracing.py` | `TraceContext`, `TraceSpanName` |
| `metrics.py` | `MetricName`, `MetricKind`, `prometheus_name()` |

Metric catalog: `docs/contracts/observability-metrics.md`.

## Usage

```python
from gpu_inference_observability import StructuredLogger, MetricName, TraceContext
```
