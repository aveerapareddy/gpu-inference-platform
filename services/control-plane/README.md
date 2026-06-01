# Control Plane

Status: Session 7 — queue ownership implemented
Implementation: In-process with API gateway; waiting queue through QUEUED; no scheduler

## Ownership

Process: `services/control-plane`. Package: `control_plane`.

Per-request lifecycle through `QUEUED`. The waiting queue owns admitted workload
until a scheduler exists. The queue does not schedule, batch, or run inference.

## Responsibilities (implemented)

- Application bootstrap with `startup()` / `shutdown()`
- Request registry and lifecycle manager
- **Waiting queue** (`queue/`): FIFO enqueue, dequeue, peek, size, contains, remove, clear
- Queue data structures: `QueuedRequest`, `WaitingQueue`, `QueueSnapshot`, `QueueStatistics`
- Queue timing: `queue_entered_at`, `queue_position`, `queue_wait_duration_ms`, `request_age_ms`
- Capacity: `max_queue_size`, `queue_timeout_ms`; overflow → `REJECTED` (`queue_full`)
- Queue events: `request_enqueued`, `request_dequeued`, `queue_full`, `queue_timeout`, `queue_removed`
- Inspection: `get_queue_snapshot()`, `get_queue_statistics()`, `list_queued_requests()`
- Gateway handoff: `RECEIVED` → `VALIDATED` → `ADMITTED` → enqueue → `QUEUED`

## Responsibilities (not implemented)

- HTTP APIs
- Priority ordering (FIFO only)
- Scheduler dequeue driving lifecycle past `QUEUED`
- Batching, routing, inference, streaming
- Persistence, Prometheus export

## Lifecycle and queue (Session 7 stopping point)

```
RECEIVED → VALIDATED → ADMITTED → [enqueue] → QUEUED (in waiting queue)
```

On enqueue:

- Registry state → `QUEUED`
- `queue_entered_at` and `queue_position` recorded on `RegisteredRequest`
- `request_enqueued` event emitted with position and correlation id

On capacity exceeded:

- `queue_full` event
- Request → `REJECTED` (not enqueued)

On queue timeout:

- `queue_timeout` event
- Request → `TIMED_OUT` (removed from queue)

## Queue operations

| Operation | Behavior |
| --- | --- |
| `enqueue` | Tail append; assign position; reject if at `max_queue_size` |
| `dequeue` | Remove head (for future scheduler) |
| `peek` | View head without remove |
| `size` / `contains` | Queue depth and membership |
| `remove` | Remove arbitrary id; emit `queue_removed` |
| `clear` | Drop all waiting items |

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `CONTROL_PLANE_MAX_QUEUE_SIZE` | 1000 | Max waiting requests |
| `CONTROL_PLANE_QUEUE_TIMEOUT_MS` | 300000 | Max wait in queue before `TIMED_OUT` |
| `CONTROL_PLANE_REGISTRY_MAX_ENTRIES` | 10000 | Registry capacity |

## Inspection (internal)

```python
app.queue.get_queue_snapshot()
app.queue.get_queue_statistics()
app.queue.list_queued_requests()
```

## Layout

```
src/control_plane/
  queue/
    models.py           data structures
    waiting_queue.py    FIFO operations
    capacity.py         overflow rules
    service.py          enqueue_from_admitted
    inspection.py       snapshot and stats
  lifecycle/manager.py  calls queue after ADMITTED
```
