# Runtime State Models

Status: Architecture Phase (Session 2 — contracts locked)
Implementation: Not Started

Canonical enums: `packages/common-schemas/schemas/enums.json`.

Session 1 defined operational behavior in `docs/architecture/runtime-model.md`.
This document defines contract-level state machines: allowed transitions,
invalid transitions, terminal states, and failure states.

## RequestState

Platform-owned request lifecycle.

### Values

| State | Terminal | Failure |
| --- | --- | --- |
| `received` | no | no |
| `validated` | no | no |
| `admitted` | no | no |
| `queued` | no | no |
| `scheduled` | no | no |
| `prefilling` | no | no |
| `decoding` | no | no |
| `streaming` | no | no |
| `completed` | yes | no |
| `failed` | yes | yes |
| `timed_out` | yes | yes |
| `rejected` | yes | yes |
| `cancelled` | yes | no |

### Allowed transitions

```
received -> validated | cancelled | failed
validated -> admitted | rejected | cancelled
admitted -> queued | scheduled | rejected | cancelled | failed
queued -> scheduled | rejected | timed_out | cancelled
scheduled -> prefilling | failed | timed_out | cancelled
prefilling -> decoding | failed | timed_out | cancelled
decoding -> streaming | completed | failed | timed_out | cancelled
streaming -> completed | cancelled | failed
```

Non-streaming may transition `decoding -> completed` without entering `streaming`.

### Invalid transitions (contract violation if observed)

- Any transition out of a terminal state
- `queued -> prefilling` (must pass through `scheduled`)
- `received -> admitted` (must pass through `validated`)
- `completed -> *`

### Failure states

`failed`, `timed_out`, `rejected` require `FailureRecord.failure_reason`.

## BatchState

Scheduler and adapter view of a dispatch unit.

### Values

| State | Terminal | Failure |
| --- | --- | --- |
| `forming` | no | no |
| `dispatched` | no | no |
| `prefilling` | no | no |
| `decoding` | no | no |
| `completed` | yes | no |
| `failed` | yes | yes |
| `cancelled` | yes | no |

### Allowed transitions

```
forming -> dispatched | cancelled
dispatched -> prefilling | failed | cancelled
prefilling -> decoding | failed | cancelled
decoding -> completed | failed | cancelled
```

### Invalid transitions

- `forming -> decoding` (skip dispatch)
- `completed -> *`
- `failed -> *`

### Notes

- `forming`: scheduler assembling assignments
- `dispatched`: RPC to adapter accepted
- Terminal `failed` fails all assignments in batch unless partial success is
  explicitly defined in a future session (v1: all fail)

## BackendState

Inference worker as seen by adapter and control plane.

### Values

| State | Terminal | Failure |
| --- | --- | --- |
| `registering` | no | no |
| `idle` | no | no |
| `busy` | no | no |
| `draining` | no | no |
| `unhealthy` | yes | yes |
| `offline` | yes | no |

### Allowed transitions

```
registering -> idle | unhealthy
idle -> busy | draining | unhealthy | offline
busy -> idle | unhealthy
draining -> idle | offline
unhealthy -> offline
idle -> offline
```

### Invalid transitions

- `offline -> busy` without new `registering` cycle
- `unhealthy -> busy` without passing through `idle` after recovery policy

### Behavior

| State | Scheduler may dispatch |
| --- | --- |
| `idle` | yes, if capacity available |
| `busy` | yes, if capacity slots remain |
| `draining` | no new batches |
| `unhealthy`, `offline` | no |

## SchedulerState

Aggregate scheduler process mode (not per-request).

### Values

| State | Terminal | Failure |
| --- | --- | --- |
| `starting` | no | no |
| `accepting` | no | no |
| `saturated` | no | no |
| `draining` | no | no |
| `unavailable` | yes | yes |

### Allowed transitions

```
starting -> accepting | unavailable
accepting -> saturated | draining | unavailable
saturated -> accepting | draining | unavailable
draining -> unavailable
```

### Invalid transitions

- `unavailable -> saturated` (must go through `starting` or `accepting`)
- `draining -> accepting` without operator action (v1: restart required)

### Mode behavior

| State | Admission |
| --- | --- |
| `accepting` | Normal admit/reject |
| `saturated` | Stricter reject thresholds; same contract, higher `queue_full` rate |
| `draining` | Reject new work; drain queue |
| `unavailable` | Reject all with `internal_error` |

## Cross-model consistency

| Platform RequestState | BatchState (if assigned) | BackendState |
| --- | --- | --- |
| `scheduled` | `forming` or `dispatched` | `idle` or `busy` |
| `prefilling` | `prefilling` | `busy` |
| `decoding` | `decoding` | `busy` |
| `completed` | `completed` | `idle` or `busy` |

Mismatch between request and batch state is a contract violation logged as
`internal_error`.
