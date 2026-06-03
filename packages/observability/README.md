# Observability Package

**Status:** Session 12 tracing + Session 13 Prometheus metrics implemented.

## Modules

| Module | Status | Purpose |
| --- | --- | --- |
| `logging.py` | Session 3 | Structured JSON logs |
| `tracing.py` | Session 3 | Span name contracts |
| `metrics.py` | Session 3 | Metric name/kind contracts (catalog) |
| `runtime/` | Session 12 | In-memory request traces |
| `registry/` | Session 13 | Prometheus metrics registry and recorder |

## Prometheus export

Embedded stack exposes metrics via gateway `GET /metrics` when `GATEWAY_FULL_PATH_INTEGRATED=true`.

```bash
curl -s localhost:8000/metrics
```

Registry: `gpu_inference_observability.registry.MetricsRegistry`

## Documentation

- Tracing: [docs/architecture/observability-runtime.md](../../docs/architecture/observability-runtime.md)
- Metrics: [docs/architecture/metrics-model.md](../../docs/architecture/metrics-model.md)

## Validation

```bash
python tests/integration/session12_trace_validation.py
python tests/integration/session13_metrics_validation.py
```

## Not implemented

Grafana dashboards, alerts, OpenTelemetry export, GPU metrics, persistent metric storage.
