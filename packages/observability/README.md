# Observability Package

**Status:** Session 12 tracing + Session 13 metrics + Session 14 OpenTelemetry spans + Session 15 failure injection.

## Modules

| Module | Status | Purpose |
| --- | --- | --- |
| `logging.py` | Session 3 | Structured JSON logs |
| `tracing.py` | Session 3 | Span name contracts (pre-OTel) |
| `metrics.py` | Session 3 | Metric name/kind contracts |
| `runtime/` | Session 12 | In-memory request event traces |
| `registry/` | Session 13 | Prometheus metrics registry |
| `otel/` | Session 14 | OpenTelemetry trace manager and exporters |
| `failure_injection/` | Session 15 | Deterministic failure injection config and injector |

## OpenTelemetry

```python
from gpu_inference_observability.otel import TraceManager, TraceExportConfig, TraceExporterType

manager = TraceManager(TraceExportConfig(exporter=TraceExporterType.CONSOLE))
with manager.span("request", component="gateway", request_id=rid, correlation_id=cid):
    ...
manager.force_flush()
```

Embedded stack: `create_platform_stack()` wires one shared `TraceManager` (memory exporter by default).

## Prometheus export

Gateway `GET /metrics` when embedded stack is enabled.

## Documentation

- Event traces: [docs/architecture/observability-runtime.md](../../docs/architecture/observability-runtime.md)
- Metrics: [docs/architecture/metrics-model.md](../../docs/architecture/metrics-model.md)
- OTel spans: [docs/architecture/tracing-model.md](../../docs/architecture/tracing-model.md)
- Failure model: [docs/architecture/failure-model.md](../../docs/architecture/failure-model.md)

## Validation

```bash
python tests/integration/session12_trace_validation.py
python tests/integration/session13_metrics_validation.py
python tests/integration/session14_otel_validation.py
python runtime-validation/run_validation.py
```

## Not implemented

Jaeger, Tempo, Grafana, alerting, collector deployment, cross-process W3C propagation.
