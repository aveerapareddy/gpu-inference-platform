# Control Plane

Status: Session 6 — gateway-integrated lifecycle through QUEUED
Implementation: In-process with API gateway; no HTTP server; no scheduler

## Ownership

Process: `services/control-plane`. Package: `control_plane`.

Per-request lifecycle authority: registration, validated transitions, admission
framework, stop at `QUEUED`. Model registry HTTP and durable storage remain
Future Work.

## Responsibilities (implemented)

- Application bootstrap with `startup()` / `shutdown()`
- In-memory request registry with query APIs
- Lifecycle progression: `RECEIVED` → `VALIDATED` → `ADMITTED` → `QUEUED`
- Transition validation per `docs/contracts/state-models.md`
- Admission framework extension points (default: accept)
- Scheduler client interface + stub (no scheduling)
- Lifecycle events: `request_received`, `request_validated`, `request_admitted`, `request_queued`, plus rejection/failure events
- Failure states retained in registry (`REJECTED`, `FAILED`)
- `RegistryQueries`: status, details, list active, list by state
- `LifecycleManager.process_through_queued()` for gateway handoff

## Responsibilities (not implemented)

- HTTP APIs
- States beyond `QUEUED` (`SCHEDULED`, `PREFILLING`, inference path)
- Scheduler logic, batching, routing
- Inference execution, streaming
- Admission policies with real limits
- Persistence, retry logic
- Metrics export

## Lifecycle (Session 6 stopping point)

```
RECEIVED → VALIDATED → ADMITTED → QUEUED
                ↓           ↓
            REJECTED    REJECTED (admission)
                ↓
             FAILED (internal error)
```

Invalid examples (raise `InvalidTransitionError`):

- `VALIDATED` → `RECEIVED`
- `COMPLETED` → `QUEUED`
- `QUEUED` → `PREFILLING` (not enabled until scheduler session)

## Gateway integration

Gateway embeds `ControlPlaneApplication` via `IntegratedControlPlaneClient`
(`services/api-gateway`). On each completion request:

1. Gateway validates HTTP input and builds `SubmitRequest`
2. `accept_request()` runs `process_through_queued()`
3. Gateway returns placeholder response; request remains `QUEUED` in registry

## Registry queries

```python
app.queries.get_status(request_id)
app.queries.get_details(request_id)
app.queries.list_active()
app.queries.list_by_state(RequestState.QUEUED)
```

## Run (standalone process)

```bash
pip install -e packages/common-schemas -e packages/observability -e services/control-plane
gpu-inference-control-plane
```

No HTTP listener. Use gateway for integrated path.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `CONTROL_PLANE_REGISTRY_MAX_ENTRIES` | 10000 | Registry capacity |

## Layout

```
src/control_plane/
  application.py
  lifecycle/manager.py    process_through_queued
  registry/memory.py      in-memory store + list_* 
  registry/queries.py     read API
  admission/              framework + protocols
  scheduler/              client + stub
  failures/               categories + framework
  observability/events.py lifecycle log events
```
