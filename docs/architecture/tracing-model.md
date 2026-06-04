# Distributed Tracing Model

**Status:** Implemented (Session 14). OpenTelemetry SDK with pluggable exporters.

**Not implemented:** Jaeger, Tempo, Grafana, dashboards, alerting, collector deployment.

## Foundation

| Component | Module | Role |
| --- | --- | --- |
| `TraceManager` | `gpu_inference_observability.otel.manager` | Tracer provider, span creation, context propagation |
| `SpanScope` | `gpu_inference_observability.otel.scope` | Attribute helpers, error instrumentation |
| `TraceExportConfig` | `gpu_inference_observability.otel.config` | Exporter selection |
| `InMemorySpanExporter` | `gpu_inference_observability.otel.exporters` | Test and embedded validation |
| `TraceSpanInspector` | `gpu_inference_observability.otel.inspector` | Span hierarchy validation |

Dependencies: `opentelemetry-api`, `opentelemetry-sdk`, `opentelemetry-exporter-otlp-proto-http`.

Session 3 `gpu_inference_observability.tracing.TraceContext` remains a header contract scaffold. Session 12 `runtime.TraceContext` remains the in-memory event trace model. Session 14 OpenTelemetry spans are separate.

## Exporter Configuration

`TraceExportConfig.exporter`:

| Value | Behavior |
| --- | --- |
| `memory` | Default in `create_platform_stack()`. Spans stored in process for validation. |
| `console` | Writes spans to stdout via `ConsoleSpanExporter`. |
| `otlp` | Sends spans to configured OTLP HTTP endpoint. No collector deployed by this repo. |
| `none` | Tracer provider without export processor. |

No Jaeger or Tempo deployment. OTLP endpoint is configuration only.

## Span Hierarchy

Parent span: `request` (gateway).

Child spans (in typical success order):

| Span | Owner component | Collection point |
| --- | --- | --- |
| `validation` | control_plane | `LifecycleManager.process_through_queued` |
| `admission` | control_plane | `LifecycleManager.process_through_queued` |
| `queue` | control_plane | `QueueService.enqueue_from_admitted` |
| `scheduler` | scheduler | `RequestPathOrchestrator.execute_full_path` |
| `batch` | scheduler | `ContinuousBatchEngine._place_selected_locked` |
| `backend_submission` | adapter | `InferenceAdapterApplication.submit_batch` |
| `completion` | control_plane | `LifecycleManager.complete_request` |

All child spans use OpenTelemetry context propagation (`start_as_current_span`) so parent-child relationships are preserved in-process.

## Propagation Model

Embedded stack (single process):

1. Gateway opens root `request` span in `IntegratedPlatformClient.accept_request`.
2. Control plane, queue, scheduler, batch engine, and adapter create child spans under the active context.
3. `request_id` and `correlation_id` are set as span attributes on each span.
4. `batch_id` and `backend_id` are added when known.

No HTTP trace header injection in Session 14. Context propagates via OpenTelemetry contextvars within the embedded runtime.

## Span Attributes

Standard attributes (`gpu_inference_observability.otel.attributes.SpanAttributes`):

| Attribute | Set when |
| --- | --- |
| `request_id` | Span creation |
| `correlation_id` | Span creation (`RequestContext.trace_id`) |
| `batch_id` | Batch placement or backend dispatch |
| `backend_id` | Backend submission |
| `request_state` | Lifecycle transitions |
| `batch_state` | Batch engine operations |
| `failure_type` | Error instrumentation |
| `failure_reason` | Error instrumentation |
| `component_name` | Every span |
| `model` | When model is known |

## Error Instrumentation

`SpanScope` methods:

| Method | Use |
| --- | --- |
| `record_exception(exc)` | Unexpected exceptions |
| `record_failure(type, reason)` | Generic failure with attributes + span event |
| `record_rejection(reason)` | Admission, queue, backend rejections |
| `record_timeout(reason)` | Queue timeout paths |

Failures appear as span attributes, span events, and ERROR status. No alerting or retry logic.

Recorded at:

- Admission reject: `admission` span
- Queue full: `queue` span
- Batch reject: `batch` span or orchestrator batch path
- Scheduler skip/failure: `scheduler` span
- Backend reject: `backend_submission` span

## Wiring

`create_platform_stack()` creates one shared `TraceManager` and passes it to control plane, scheduler, and adapter factories.

`PlatformStack.shutdown()` calls `trace_manager.force_flush()`.

## Process Singleton

OpenTelemetry permits one global `TracerProvider` per process. `TraceManager` installs the provider on first construction and reuses it for subsequent instances. All `TraceManager` instances share the same in-memory exporter when configured with `memory`.

Validation tests call `TraceManager.clear_collected_spans()` between scenarios.

## Limitations

- One global `TracerProvider` per process; exporter type is fixed at first `TraceManager` construction
- In-process context propagation only; no cross-process W3C traceparent on internal calls
- No span sampling configuration
- No exemplars linking metrics and traces
- Memory exporter clears on process exit
- Duplicate `scheduler` spans possible on some failure paths (cycle wrapper + orchestrator failure recording)

## Validation

```bash
python tests/integration/session14_otel_validation.py
```

Scenarios: successful hierarchy, admission rejection, scheduler batch rejection, backend rejection.

## Related

- Runtime event traces: [observability-runtime.md](./observability-runtime.md)
- Prometheus metrics: [metrics-model.md](./metrics-model.md)
