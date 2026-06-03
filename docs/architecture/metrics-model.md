# Metrics Model

**Status:** Implemented (Session 13). Prometheus export via gateway `GET /metrics`.

**Not implemented:** Grafana dashboards, alerts, autoscaling signals, GPU metrics, derived throughput metrics.

## Registry

| Component | Module | Role |
| --- | --- | --- |
| `MetricsRegistry` | `gpu_inference_observability.registry.registry` | Defines and owns all Prometheus instruments |
| `RuntimeMetricsRecorder` | `gpu_inference_observability.registry.recorder` | Semantic record methods used by services |
| Export | `MetricsRegistry.export_prometheus()` | Prometheus text format |
| HTTP | `api_gateway.routers.metrics` | `GET /metrics` on embedded stack |

All metric names use prefix `gpu_inference_`. One shared `MetricsRegistry` instance is created in `create_platform_stack()` and passed to control plane, scheduler, and adapter factories.

## Request Metrics

| Name | Type | Owner | Source | Collection point | Intended use |
| --- | --- | --- | --- | --- | --- |
| `gpu_inference_requests_received_total` | counter | control plane | lifecycle | `LifecycleEventEmitter.emit` on `request_received` | Request arrival rate |
| `gpu_inference_requests_completed_total` | counter | control plane | lifecycle | `LifecycleEventEmitter.emit` on `request_completed` | Successful completion rate |
| `gpu_inference_requests_failed_total` | counter | control plane | lifecycle / queue | `request_failed`, queue timeout | Failure rate |
| `gpu_inference_requests_rejected_total` | counter | control plane | lifecycle / queue | `request_rejected`, `queue_full` | Admission/queue rejection rate |
| `gpu_inference_active_requests` | gauge | control plane | lifecycle | inc on received, dec on terminal | In-flight request count |
| `gpu_inference_request_duration_seconds` | histogram | control plane | lifecycle | observe on terminal state | End-to-end request latency distribution |

Units: counter (count), gauge (count), histogram (seconds).

## Queue Metrics

| Name | Type | Owner | Source | Collection point | Intended use |
| --- | --- | --- | --- | --- | --- |
| `gpu_inference_queue_depth` | gauge | control plane | queue | `QueueService` after enqueue/dequeue/timeout | Current backlog |
| `gpu_inference_queue_enqueue_total` | counter | control plane | queue | `LifecycleEventEmitter.emit_queue` on `request_enqueued` | Enqueue rate |
| `gpu_inference_queue_dequeue_total` | counter | control plane | queue | `emit_queue` on `request_dequeued` | Dequeue rate |
| `gpu_inference_queue_timeout_total` | counter | control plane | queue | `emit_queue` on `queue_timeout` | Timeout rate |
| `gpu_inference_queue_wait_duration_seconds` | histogram | control plane | queue | `emit_queue` with `queue_wait_duration_ms` | Queue wait time distribution |

Units: gauge (count), counter (count), histogram (seconds).

## Scheduler Metrics

| Name | Type | Owner | Source | Collection point | Intended use |
| --- | --- | --- | --- | --- | --- |
| `gpu_inference_scheduler_cycles_total` | counter | scheduler | cycle runner | `SchedulingCycleRunner._run_cycle_locked` | Cycle throughput |
| `gpu_inference_scheduler_selection_total` | counter | scheduler | cycle runner | end of successful cycle | Selected request count |
| `gpu_inference_scheduler_skip_total` | counter | scheduler | cycle runner | end of successful cycle | Skipped request count |
| `gpu_inference_scheduler_failures_total` | counter | scheduler | cycle runner | cycle exception handler | Scheduler error rate |
| `gpu_inference_scheduler_cycle_duration_seconds` | histogram | scheduler | cycle runner | cycle start to end | Cycle latency distribution |

These metrics describe scheduling decisions only. No model execution or token generation.

Units: counter (count), histogram (seconds).

## Batch Metrics

| Name | Type | Owner | Source | Collection point | Intended use |
| --- | --- | --- | --- | --- | --- |
| `gpu_inference_batches_created_total` | counter | scheduler | batch engine | `_create_batch` | Batch creation rate |
| `gpu_inference_active_batches` | gauge | scheduler | batch engine | non-terminal batch count | Open batch count |
| `gpu_inference_batch_size` | histogram | scheduler | batch engine | successful admission | Member count at admission |
| `gpu_inference_batch_admissions_total` | counter | scheduler | batch engine | successful `place_selected` | Admission rate |
| `gpu_inference_batch_failures_total` | counter | scheduler | batch engine | `_fail_batch_locked` | Batch failure rate |
| `gpu_inference_batch_lifetime_seconds` | histogram | scheduler | batch engine | batch complete/fail | Batch lifetime distribution |

Units: counter (count), gauge (count), histogram (count or seconds as labeled).

## Backend Metrics

| Name | Type | Owner | Source | Collection point | Intended use |
| --- | --- | --- | --- | --- | --- |
| `gpu_inference_backend_submissions_total` | counter | inference adapter | `submit_batch` | before backend call | Submission rate |
| `gpu_inference_backend_acceptance_total` | counter | inference adapter | `submit_batch` | accepted result | Acceptance rate |
| `gpu_inference_backend_rejections_total` | counter | inference adapter | `submit_batch` | rejected result / `BackendRejected` | Rejection rate |
| `gpu_inference_backend_failures_total` | counter | inference adapter | `submit_batch` | internal exception | Adapter/backend error rate |
| `gpu_inference_backend_request_duration_seconds` | histogram | inference adapter | `submit_batch` | backend call wall time | Backend call latency |

Label: `backend_id`. No GPU utilization or memory metrics.

Units: counter (count), histogram (seconds).

## Export

```
GET /metrics
Content-Type: text/plain; version=0.0.4; charset=utf-8
```

Available when `GATEWAY_FULL_PATH_INTEGRATED=true` (default). Returns empty body when embedded stack is disabled.

## Limitations

- In-process registry only; metrics reset on process restart
- Single gateway process exposes one `/metrics` target for the embedded stack
- No exemplars, no remote write, no service-level metric federation
- Session 3 contract enum (`gpu_inference_observability.metrics.MetricName`) is a separate catalog; Session 13 runtime names above are the implemented set

## Validation

```bash
python tests/integration/session13_metrics_validation.py
```

## Related

- Runtime tracing: [observability-runtime.md](./observability-runtime.md)
- Contract catalog (not all names implemented): `docs/contracts/observability-metrics.md`
