# Scheduler

Status: Session 11 — integrated in gateway full path through mock completion
Implementation: In-process with control plane queue reader; no HTTP server

## Ownership split

| Component | Owner | Responsibility |
| --- | --- | --- |
| Work selection | Scheduler loop | Policy-driven candidate selection (`SchedulerPolicy`) |
| Batch placement | Batching engine | Admission, membership, lifecycle |
| Backend dispatch | Scheduler `BatchDispatchService` | Build `DispatchBatch`, submit via `AdapterClient` |
| Queue storage | Control plane | Enqueue/dequeue, queue timing |
| Backend execution | Inference adapter | Contract + mock acknowledge; no tokens |

The scheduler selects work. The batching engine owns placement into managed batches.

## Scheduler responsibilities (implemented)

- Tick loop and queue inspection (read-only)
- Policy selection up to `max_candidate_requests` (default: FIFO; also SJF, latency-aware, fairness)
- Hand selected requests to batching engine each cycle
- Dispatch: `BatchDispatchService` submits `FILLING`/`READY`/`ACTIVE` batches to adapter after each cycle
- `SchedulingResult.dispatch_results` records adapter accept/reject

## Batching responsibilities (implemented)

- Contracts: `Batch`, `BatchMember`, `BatchContext`, `BatchResult`, `BatchSnapshot`
- State machine: `CREATED` → `FILLING` → `READY` → `ACTIVE` → terminal
- Continuous engine: admit to active batch, retire members, reuse slots
- Active set: `add_request`, `remove_request`, `replace_request`, `list_active_requests`
- Admission rules: `max_batch_size`, `max_active_requests`, `batch_admission_window_ms`
- Decisions: `BatchPlacementDecision`, `BatchRejectionDecision`, `BatchAssignment`
- Inspection: `get_batch`, `list_batches`, `get_active_batch`, `get_batch_snapshot`, `get_batch_statistics`
- Events: `batch_created`, `batch_admission`, `batch_full`, `request_added_to_batch`, `request_removed_from_batch`, `batch_completed`, `batch_failed`

## Not implemented

- HTTP APIs
- Inference execution, token generation, vLLM SDK
- Lifecycle transition past `QUEUED`
- Routing, streaming
- Scheduler optimization, predictive or ML-driven scheduling
- Metrics backend export

## Scheduler-to-batch handoff

Each cycle:

1. Scan queue → evaluate candidates via configured `SchedulerPolicy`
2. For each selected request, call `BatchService.place_selected(queue_item)`
3. Batching engine evaluates admission rules
4. Accepted → `BatchPlacementDecision` with `BatchAssignment`
5. Rejected → `BatchRejectionDecision` with reason
6. `SchedulingResult` includes `placement_decisions`, `rejection_decisions`, `dispatch_results`

## Scheduler-to-adapter handoff (Session 10)

After batch placement, `BatchDispatchService` builds `common_schemas.batch.Batch` from
stored assignments and calls `AdapterClient.submit_batch()`. Adapter forwards to
registered backend (mock by default). No routing; uses `SCHEDULER_DEFAULT_BACKEND_ID`.

```python
from inference_adapter import create_application
from scheduler.integrations.embedded_adapter import EmbeddedAdapterClient

adapter = create_application()
await adapter.startup()
sched = create_application(reader, adapter_client=EmbeddedAdapterClient(adapter))
```

Queue entries are not dequeued. Batch membership is separate from queue state.

## Batch state machine

| State | Terminal | Notes |
| --- | --- | --- |
| `created` | no | Batch record created |
| `filling` | no | Accepting members within admission window |
| `ready` | no | Window closed or batch full |
| `active` | no | Continuous membership; slots reused on retire |
| `completed` | yes | All members retired |
| `failed` | yes | Batch-level failure |
| `cancelled` | yes | Not wired in Session 9 |

Invalid: any transition out of terminal states; `created` → `active` (must pass through `filling`).

## Failure behavior

| Condition | Behavior |
| --- | --- |
| Queue empty | Cycle completes; no selections or placements |
| Batch full | `batch_full` event; new requests rejected until slot frees |
| `max_active_requests` | `BatchRejectionDecision` with `max_active_requests_reached` |
| Admission window closed | Filling batch stops accepting; new batch created on next admit |
| Member retire on ACTIVE batch | Slot freed; continuous admission resumes |
| Member fail | Batch → `FAILED`; `batch_failed` event |

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `SCHEDULER_MAX_CANDIDATE_REQUESTS` | 10 | Max queue selections per cycle |
| `SCHEDULER_TICK_INTERVAL_MS` | 1000 | Scheduler loop interval |
| `SCHEDULER_QUEUE_SCAN_LIMIT` | 100 | Max queue items scanned |
| `SCHEDULER_MAX_BATCH_SIZE` | 8 | Max active members per batch |
| `SCHEDULER_MAX_ACTIVE_REQUESTS` | 32 | Global active member cap |
| `SCHEDULER_BATCH_ADMISSION_WINDOW_MS` | 5000 | Filling window before READY |

## Embedded wiring

```python
from control_plane import create_application as create_control_plane
from scheduler import ControlPlaneQueueReader, create_application

cp = create_control_plane()
await cp.startup()

sched = create_application(ControlPlaneQueueReader(cp.queue))
await sched.startup()

result = await sched.run_scheduling_cycle()
batch = sched.batch.get_active_batch("demo")
stats = sched.batch.get_batch_statistics()

# Retire without inference (test/lifecycle hook)
sched.batch.complete_request(request_id)
```

## Layout

```
src/scheduler/
  batch/
    models.py           contracts and BatchState
    transitions.py      state machine
    engine.py             continuous batching
    admission.py          admission rules
    active_set.py         member tracking
    inspection.py         snapshots and stats
    service.py              facade
  loop/cycle.py           selection + batch handoff
  models/batch_decision.py
  observability/batch_events.py
```

## Type naming

- `scheduler.batch.models.BatchState` — batch management lifecycle (Session 9)
- `common_schemas.states.BatchState` — adapter execution lifecycle (not used until dispatch)
- `common_schemas.batch.Batch` — dispatch unit schema (future adapter handoff)
