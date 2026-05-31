# Control Plane

Status: Session 5 — lifecycle and frameworks implemented
Implementation: In-process library; no HTTP server; no scheduler connection

## Ownership

Process: `services/control-plane`. Package: `control_plane`.

Per-request lifecycle authority for Session 5: registration, state transitions,
and admission framework orchestration. Model registry HTTP and durable storage
remain Future Work.

## Responsibilities (implemented)

- Application bootstrap with `startup()` / `shutdown()`
- In-memory request registry (register, get, update state, remove)
- Lifecycle manager with transition validation (`docs/contracts/state-models.md`)
- Admission framework extension points (default: accept all)
- Scheduler client interface + stub (no submit behavior)
- Lifecycle event emission via structured logs
- Failure classification framework (validation, admission, scheduler, backend, internal)

## Responsibilities (not implemented)

- HTTP APIs (`/internal/v1/models`, worker registration)
- Scheduler logic, batching, routing
- Inference execution, streaming, token generation
- Admission policies (queue limits, timeouts, saturation)
- Persistence, retry logic, metrics export
- Gateway integration (handoff in a later session)

## Lifecycle

Allowed transitions enforced in `lifecycle/transitions.py`. Example path:

```
VALIDATED → ADMITTED → QUEUED → SCHEDULED → … → COMPLETED
```

Terminal states remove the entry from the registry after the transition event.

| Method | Purpose |
| --- | --- |
| `lifecycle.register(submit)` | Register at `VALIDATED`; emit `request_created` |
| `lifecycle.run_admission(id)` | `VALIDATED` → `ADMITTED` or `REJECTED` |
| `lifecycle.transition(id, state)` | Validated state change + event |
| `lifecycle.handoff_to_scheduler(id)` | Calls stub only; no scheduling |

## Interfaces

| Module | Type |
| --- | --- |
| `admission/interfaces.py` | `AdmissionEvaluator`, `QueueCapacityCheck`, `TimeoutCheck`, `PolicyEvaluator` |
| `admission/framework.py` | `AdmissionFramework` |
| `scheduler/client.py` | `SchedulerClient` |
| `scheduler/stub.py` | `StubSchedulerClient` |
| `failures/categories.py` | `ValidationFailure`, `AdmissionFailure`, … |
| `failures/framework.py` | `FailureFramework` propagation rules |

## Lifecycle events

Emitted as structured logs (`lifecycle_event=true`):

- `request_created`
- `request_admitted`
- `request_queued`
- `request_rejected`
- `request_failed`
- `request_completed`

## Run (process placeholder)

```bash
pip install -e packages/common-schemas -e packages/observability -e services/control-plane
gpu-inference-control-plane
```

Program blocks until interrupted; no HTTP listener.

## Example (library)

```python
import asyncio
from common_schemas.inference_request import SubmitRequest
from control_plane import create_application

async def demo():
    app = create_application()
    await app.startup()
    submit = ...  # SubmitRequest from gateway
    entry = app.lifecycle.register(submit)
    await app.lifecycle.run_admission(entry.request_id)
    await app.shutdown()

asyncio.run(demo())
```

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `CONTROL_PLANE_REGISTRY_MAX_ENTRIES` | 10000 | Registry capacity |
| `CONTROL_PLANE_REMOVE_TERMINAL_AFTER_SECONDS` | 3600 | Reserved for future cleanup |

## Layout

```
src/control_plane/
  application.py       ControlPlaneApplication
  lifecycle/           manager, transitions
  registry/            InMemoryRequestRegistry
  admission/           framework + protocols
  scheduler/           client + stub + types
  failures/            categories + framework
  observability/       LifecycleEventEmitter
```
