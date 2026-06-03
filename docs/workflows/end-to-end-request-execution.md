# End-to-End Request Execution

Status: Session 11 — embedded full path implemented
Implementation: In-process gateway stack; mock backend; no tokens or GPU

## Request path

```
Client HTTP POST
  → API Gateway (auth, validate, build SubmitRequest)
  → Control Plane lifecycle (RECEIVED → VALIDATED → ADMITTED)
  → Queue (QUEUED)
  → Scheduler cycle (select FIFO candidates)
  → Batch engine (SCHEDULED → BATCHED placement)
  → Inference adapter (build DispatchBatch, submit)
  → Mock backend (acknowledge, no execution)
  → Control Plane (SUBMITTED → COMPLETED, batch member retired)
  → Gateway placeholder completion response
```

All components run in the gateway process when `GATEWAY_FULL_PATH_INTEGRATED=true`.

## Component ownership

| Stage | Owner | Output state |
| --- | --- | --- |
| HTTP intake | API Gateway | — |
| Validation | API Gateway | — |
| Lifecycle (early) | Control Plane | RECEIVED through QUEUED |
| Queue storage | Control Plane | QUEUED |
| Work selection | Scheduler | SCHEDULED |
| Batch membership | Scheduler batch engine | BATCHED |
| Backend handoff | Inference adapter | SUBMITTED |
| Terminal success | Control Plane | COMPLETED |

## Lifecycle transitions (Session 11)

```
RECEIVED → VALIDATED → ADMITTED → QUEUED
  → SCHEDULED → BATCHED → SUBMITTED → COMPLETED
```

Terminal failure states: REJECTED, FAILED, TIMED_OUT, CANCELLED.

`BATCHED` and `SUBMITTED` are Session 11 additions to `RequestState`.

Transitions are enforced in `control_plane/lifecycle/transitions.py`.
Invalid transitions raise `InvalidTransitionError`.

## Trace context

Propagated on `RegisteredRequest` and lifecycle event `extra` fields:

| Field | Set when |
| --- | --- |
| `request_id` | Gateway creates request |
| `correlation_id` | `RequestContext.trace_id` on all lifecycle events |
| `batch_id` | Scheduler placement |
| `backend_id` | Adapter dispatch accept |

## Failure paths

| Failure point | Typical state | Mechanism |
| --- | --- | --- |
| Gateway validation | HTTP 4xx | No registry entry |
| Admission / queue full | REJECTED | Control plane before scheduler |
| Queue timeout | TIMED_OUT | Queue service expiry |
| Batch placement reject | FAILED | Orchestrator after scheduler cycle |
| Adapter / backend reject | FAILED | Dispatch `accepted=false` or adapter error |
| Invalid transition | HTTP 500 | Lifecycle guard |

Failure propagation: registry state updated, `failure_reason` set where applicable, lifecycle event emitted.

No automatic retries.

## Completion handling (Session 11)

On mock backend accept:

1. Lifecycle `SUBMITTED`
2. Batch engine retires member (`complete_request`)
3. Lifecycle `COMPLETED`
4. `request_completed` event with trace fields

No token generation. Completion is simulated.

## Validation

Run integration scenarios:

```bash
pip install -e packages/common-schemas -e packages/observability \
  -e services/control-plane -e services/scheduler \
  -e services/inference-adapter -e services/api-gateway

python tests/integration/session11_scenarios.py
```

Scenarios: successful request, queue rejection, backend rejection, invalid transition, dispatch failure (no backend).

## Limitations

- Single-process embedding only; no HTTP between services
- Mock backend only; no vLLM, TGI, or GPU
- No streaming; `stream=true` rejected at gateway
- Placeholder HTTP response text; not model output
- No routing, worker pools, or persistence
- Scheduler tick loop runs but synchronous path uses `run_scheduling_cycle()` per request
- Performance not measured

## Related documents

- `request-serving-workflow.md` — design workflow (may predate Session 11 states)
- Service READMEs under `services/*/README.md`
