# Runtime Observability

**Status:** Implemented (Session 12). In-memory only. No Prometheus, Grafana, or OpenTelemetry export.

## Scope

| Implemented | Not implemented |
| --- | --- |
| Request trace model (`RequestTrace`, `TraceEvent`, `TraceTimeline`, `TraceContext`) | Prometheus metrics export |
| Lifecycle timing (`LifecycleTimestamps`, duration calculation) | Grafana dashboards |
| Structured runtime events (lifecycle, queue, scheduler, batch, backend, failure) | OpenTelemetry tracing |
| Metrics structures (`RequestMetrics`, component metrics) | GPU metrics |
| Failure records with owner and component | HTTP inspection APIs |
| `TraceInspector` snapshot interfaces | Persistent trace storage |

## Ownership

| Component | Owner module |
| --- | --- |
| Trace store and models | `gpu_inference_observability.runtime` |
| Event recording | `RuntimeEventRecorder` |
| Snapshot queries | `TraceInspector` |
| Lifecycle/queue event emission + recording | `control_plane.observability.events` |
| Scheduler/batch event emission + recording | `scheduler.observability.*` |
| Backend event emission + recording | `inference_adapter.observability.events` |
| Gateway receive timestamp | `api_gateway.runtime.integrated_client` |
| Shared store wiring | `api_gateway.runtime.stack.create_platform_stack` |

## Usage

Embedded stack (default gateway integration):

```python
from api_gateway.runtime.stack import create_platform_stack

stack = create_platform_stack()
await stack.startup()

trace = stack.trace_inspector.get_request_trace(request_id)
timeline = stack.trace_inspector.get_request_timeline(request_id)
metrics = stack.trace_inspector.get_request_metrics(request_id)
failures = stack.trace_inspector.get_request_failures(request_id)
```

## Naming

`gpu_inference_observability.tracing.TraceContext` (Session 3 span propagation) is distinct from `gpu_inference_observability.runtime.models.TraceContext` (Session 12 request identifiers). Import runtime types from `gpu_inference_observability.runtime`.

## Documentation

See [docs/architecture/observability-runtime.md](../../docs/architecture/observability-runtime.md).

## Validation

```bash
python tests/integration/session12_trace_validation.py
```
