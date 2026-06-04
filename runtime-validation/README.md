# Runtime Validation

**Status:** Implemented (Session 15). Repeatable reliability scenarios for the embedded stack.

**Not implemented:** Retries, recovery automation, distributed execution.

## Run

```bash
python runtime-validation/run_validation.py
```

Each scenario prints `ok: <name>` on success. Exit code 0 when all pass.

## Scenarios

| Scenario | Validates |
| --- | --- |
| `success_path` | End-to-end completion, baseline metrics |
| `queue_full` | REJECTED state, `requests_rejected_total`, trace failure |
| `queue_timeout` | TIMED_OUT state, `queue_timeout_total`, `requests_failed_total` |
| `queue_corruption` | Registry/queue divergence, scheduler skip, `requests_failed_total` |
| `queue_invalid_removal` | Idempotent remove on missing request |
| `scheduler_crash` | Injected cycle failure, `scheduler_failures_total` |
| `scheduler_timeout` | Injected timeout, scheduler failure metric |
| `scheduler_invalid_decision` | Phantom selected ID rejected |
| `scheduler_invalid_batch_assignment` | Injected invalid batch assignment |
| `batch_creation_failure` | Injected batch creation failure |
| `batch_admission_failure` | Injected batch admission rejection |
| `batch_cancellation` | `fail_request`, `batch_failures_total` |
| `batch_corruption` | Orphaned batch mapping |
| `backend_unavailable` | UNHEALTHY backend, request FAILED |
| `backend_timeout` | `backend_failures_total` |
| `backend_rejection` | `backend_rejections_total` |
| `backend_internal_error` | Backend exception path, OTel span |
| `lifecycle_violations` | InvalidTransitionError on terminal transitions |

## Components

- `harness.py` — `ValidationStack`, `InjectableMockBackend`, metric helpers
- `run_validation.py` — scenario runner

Failure injection config: `gpu_inference_observability.failure_injection`.

## Related

- [docs/architecture/failure-model.md](../docs/architecture/failure-model.md)
