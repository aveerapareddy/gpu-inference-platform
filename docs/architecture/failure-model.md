# Failure Model

**Status:** Implemented (Session 15). Deterministic failure injection and validation harness.

**Not implemented:** Retries, recovery automation, autoscaling, distributed failure propagation.

## Failure Categories

| Category | Owner | Terminal states | Examples |
| --- | --- | --- | --- |
| Admission | control_plane | REJECTED | Policy reject, queue full at admission |
| Queue | control_plane | REJECTED, TIMED_OUT | Queue full, wait timeout, corruption |
| Scheduler | scheduler | (request FAILED via orchestrator) | Cycle crash, timeout, invalid decision |
| Batch | scheduler | (request FAILED; batch FAILED) | Admission reject, cancellation, corruption |
| Backend | inference_adapter | FAILED | Unavailable, timeout, rejection, internal error |
| Lifecycle | control_plane | (transition blocked) | COMPLETED → QUEUED |

## Failure Injection Framework

Module: `gpu_inference_observability.failure_injection`

| Type | Role |
| --- | --- |
| `FailureInjectionConfig` | `enabled`, `point`, optional `target_request_id`, `message` |
| `FailureInjector` | `configure()`, `disable()`, `should_inject()`, `maybe_raise()` |
| `FailurePoint` | Enum of injectable failure points |
| `InjectedFailure` | Raised on injected runtime failures |

Configuration is deterministic. One active `FailurePoint` per injector instance. No random failures.

Runtime hooks:

| Component | Hook location |
| --- | --- |
| Scheduler cycle | `SchedulingCycleRunner._run_cycle_locked` — crash, timeout |
| Batch engine | `ContinuousBatchEngine._place_selected_locked` — creation, admission, invalid assignment |
| Backend | `runtime-validation/harness.InjectableMockBackend` |
| Queue | Harness helpers: `force_queue_timeout`, `corrupt_queue_without_lifecycle` |

Gateway and control plane queue full use `CPSettings(max_queue_size=N)`.

## Propagation Rules

1. Queue full during enqueue: request → REJECTED. Event: `queue_full`. Metric: `requests_rejected_total`.
2. Queue timeout: request → TIMED_OUT. Events: `queue_timeout`. Metrics: `queue_timeout_total`, `requests_failed_total`.
3. Queue corruption (registry QUEUED, not in queue): scheduler cycle empty → orchestrator marks FAILED (`scheduler_did_not_select_request`).
4. Scheduler cycle exception: cycle returns `SchedulingFailure`. Metric: `scheduler_failures_total`. Orchestrator re-raises if called via `execute_full_path`.
5. Batch rejection: orchestrator `_finalize_request` → `mark_failed(ADAPTER_ERROR)`.
6. Batch member fail: `batch.fail_request` → batch FAILED. Metric: `batch_failures_total`.
7. Backend unavailable: adapter raises `BackendUnavailable` → dispatch `accepted=false` → request FAILED.
8. Backend rejection: `backend_rejections_total`, request FAILED.
9. Backend internal error: `backend_failures_total`, OTel span exception, request FAILED.

No automatic retry. Failures are terminal unless the request remains in a non-terminal state (e.g. QUEUED after scheduler cycle failure with no finalize).

## Lifecycle Behavior

Allowed transitions: `control_plane/lifecycle/transitions.py`.

Invalid transitions raise `InvalidTransitionError`. Terminal states (COMPLETED, FAILED, REJECTED, TIMED_OUT, CANCELLED) block all outbound transitions via `is_allowed_transition()`.

`mark_failed()` uses `transition()` when allowed. Otherwise updates registry directly and emits `REQUEST_FAILED`. **Limitation:** `mark_failed()` fallback can set FAILED on a COMPLETED request without raising `InvalidTransitionError`.

## Failure Metrics

Prometheus names (prefix `gpu_inference_`):

| Session 15 name | Actual metric | When incremented |
| --- | --- | --- |
| request_failures_total | `requests_failed_total` | REQUEST_FAILED, queue timeout |
| queue_failures_total | `queue_timeout_total` + `requests_rejected_total` | No single counter |
| scheduler_failures_total | `scheduler_failures_total` | Scheduler cycle exception |
| batch_failures_total | `batch_failures_total` | `_fail_batch_locked` |
| backend_failures_total | `backend_failures_total` | Adapter internal exception |

## Observability on Failure

| Signal | Coverage |
| --- | --- |
| Structured logs | All components emit failure events |
| Runtime trace store | Queue full, queue timeout, backend reject (via event recorder) |
| OpenTelemetry spans | Rejection/failure attributes on active spans |
| Prometheus | Counters above |

Trace store failure records require `failure_reason` on lifecycle emit. Some paths (e.g. `mark_failed` before `FailureFramework.apply_to_request`) may omit trace failure records.

## Recovery Expectations

None in Session 15. Failed requests stay terminal. Queue timeout removes request from queue. Batch failure retires batch. No worker restart, no request replay.

## Validation

```bash
python runtime-validation/run_validation.py
```

## Limitations

- In-process embedded stack only
- Queue corruption and invalid removal are harness-driven, not production API
- `mark_failed()` can override terminal COMPLETED state via registry fallback
- Scheduler cycle failure leaves request QUEUED until orchestrator finalizes
- No cross-process failure propagation

## Related

- [tracing-model.md](./tracing-model.md)
- [metrics-model.md](./metrics-model.md)
- [observability-runtime.md](./observability-runtime.md)
