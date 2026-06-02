# Scheduler

Status: Session 8 — scheduling decision framework implemented
Implementation: In-process with control plane queue reader; no HTTP server

## Ownership

Process: `services/scheduler`. Package: `scheduler`.

The scheduler owns work selection from the waiting queue. It inspects queued
requests, evaluates FIFO candidates, and produces scheduling decisions. It does
not batch, dispatch, or execute inference.

## Responsibilities (implemented)

- Application bootstrap with `startup()` / `shutdown()`
- Scheduler tick loop (`tick_interval_ms`)
- Queue inspection via read-only `QueueReader` (no permanent dequeue)
- Decision models: `SchedulingCandidate`, `SchedulingDecision`, `SchedulingResult`, `SchedulingFailure`
- Runtime state: `SchedulerState`, `SchedulerCycle`, `SchedulerSnapshot`
- FIFO selection up to `max_candidate_requests` per cycle
- Control plane integration: `ControlPlaneQueueReader`
- Events: `scheduler_cycle_started`, `scheduler_cycle_completed`, `request_selected`, `request_skipped`, `scheduler_failure`

## Responsibilities (not implemented)

- HTTP APIs
- Batch formation or continuous batching
- Dispatch to inference adapter
- Lifecycle transition past `QUEUED` (no `SCHEDULED` state updates)
- Priority ordering, fairness policies, worker routing
- Metrics backend export

## Inputs

| Input | Source | Use |
| --- | --- | --- |
| Queue items | Control plane `QueueService` via `ControlPlaneQueueReader` | Candidate scan |
| `max_candidate_requests` | Config | Cap selections per cycle |
| `queue_scan_limit` | Config | Cap items read per cycle |
| `scheduler_tick_interval_ms` | Config | Loop interval |

## Outputs

| Output | Consumer | Content |
| --- | --- | --- |
| `SchedulingResult` | Future batch/dispatch layer | Selected and skipped request ids, per-request decisions |
| `SchedulerSnapshot` | Internal inspection | Cycle counts, last decision reason |
| Structured events | Logs | Cycle id, request id, decision reason, timestamp |

## Failure behavior

| Condition | Behavior |
| --- | --- |
| Empty queue | Cycle completes with `decision_reason=queue_empty`; no selections |
| Scan limit exceeded | Only first `queue_scan_limit` items evaluated |
| Candidate cap exceeded | Head selected; remainder skipped with `max_candidates_reached` |
| Cycle exception | `scheduler_failure` event; `process_mode=unavailable`; queue unchanged |

Queue entries are not removed during selection. Dequeue remains control plane ownership for future dispatch integration.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `SCHEDULER_MAX_CANDIDATE_REQUESTS` | 10 | Max requests selected per cycle |
| `SCHEDULER_TICK_INTERVAL_MS` | 1000 | Loop interval |
| `SCHEDULER_QUEUE_SCAN_LIMIT` | 100 | Max queue items scanned per cycle |

## Embedded wiring

```python
from control_plane import create_application as create_control_plane
from scheduler import ControlPlaneQueueReader, create_application

cp = create_control_plane()
await cp.startup()

reader = ControlPlaneQueueReader(cp.queue)
scheduler = create_application(reader)
await scheduler.startup()

result = await scheduler.run_scheduling_cycle()
snapshot = scheduler.get_scheduler_snapshot()
```

## Future batching integration points

- `SchedulingResult.selected_request_ids` → batch formation input
- `SchedulingDecision.decision_reason` → policy audit trail
- `QueueReader` → replace with HTTP poll when scheduler runs out-of-process
- Post-dispatch: control plane lifecycle `QUEUED` → `SCHEDULED` (not implemented)

## Layout

```
src/scheduler/
  application.py          bootstrap and snapshot
  loop/cycle.py           one scheduling cycle
  loop/runner.py          tick loop
  models/decision.py      decision types
  models/state.py         cycle and runtime state
  queue/reader.py         read-only queue protocol
  selection/fifo.py       FIFO selector
  integrations/control_plane.py
  observability/events.py
```

## Contracts

- `docs/architecture/scheduler-design.md` (design; batching not implemented)
- `common_schemas.states.SchedulerState` — aggregate process mode (`accepting`, `unavailable`, etc.)
- Local `scheduler.models.state.SchedulerState` — runtime cycle tracking (distinct type)
