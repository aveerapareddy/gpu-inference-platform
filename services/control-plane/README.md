# Control Plane

Status: Session 11 — lifecycle through COMPLETED via gateway orchestration
Implementation: Embedded in gateway full path; queue through terminal states

## Ownership

Process: `services/control-plane`. Package: `control_plane`.

Owns request registry and lifecycle transitions. Queue owns waiting workload
through `QUEUED`. Scheduler and adapter drive transitions past `QUEUED` when
gateway `RequestPathOrchestrator` runs.

## Responsibilities (implemented)

- Registry with `batch_id`, `backend_id` trace fields on `RegisteredRequest`
- Lifecycle manager: transitions through `COMPLETED` including `BATCHED`, `SUBMITTED`
- Events: `request_scheduled`, `request_batched`, `request_submitted`, `request_completed`
- Waiting queue (FIFO, capacity, timeout)
- `complete_request()` for simulated completion (no tokens)
- Failure marking with trace fields

## Responsibilities (not implemented)

- Standalone HTTP server
- Direct scheduler/adapter calls (gateway orchestrator coordinates)
- Persistence, routing, inference execution

## Lifecycle (Session 11 integrated path)

```
RECEIVED → VALIDATED → ADMITTED → QUEUED
  → SCHEDULED → BATCHED → SUBMITTED → COMPLETED
```

Failure terminals: `REJECTED`, `FAILED`, `TIMED_OUT`, `CANCELLED`.

Transitions defined in `lifecycle/transitions.py`. Invalid transitions raise
`InvalidTransitionError`.

## Integration

Gateway embeds control plane via `PlatformStack`. Orchestrator calls
`process_through_queued()` then applies post-queue transitions from scheduler
and adapter outcomes.

See `docs/workflows/end-to-end-request-execution.md`.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `CONTROL_PLANE_MAX_QUEUE_SIZE` | 1000 | Max waiting requests |
| `CONTROL_PLANE_QUEUE_TIMEOUT_MS` | 300000 | Queue wait timeout |
| `CONTROL_PLANE_REGISTRY_MAX_ENTRIES` | 10000 | Registry capacity |
