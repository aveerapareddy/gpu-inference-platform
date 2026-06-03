# Inference Adapter

Status: Session 11 — integrated in gateway full path; mock acknowledges batches
Implementation: In-process; mock backend registered by default; no HTTP server

## Ownership

Process: `services/inference-adapter`. Package: `inference_adapter`.

The adapter owns the boundary between the scheduler and inference engines.
It registers backends, accepts dispatch batches, and maps failures to a
shared vocabulary. It does not schedule, queue, or serve HTTP to clients.

## Philosophy

The scheduler submits `common_schemas.batch.Batch` payloads. The adapter selects
a registered backend by explicit `backend_id`. The backend implements
`InferenceBackend` without the scheduler knowing whether the engine is vLLM,
TGI, Hugging Face, mock, or a future runtime.

## Implemented

- `InferenceBackend` contract: `submit_batch`, `get_request_status`, `cancel_request`, `health_check`, `backend_metadata`
- Adapter-local `BackendState`: `unknown`, `starting`, `healthy`, `degraded`, `unhealthy`, `stopped`
- Backend registry: `register_backend`, `remove_backend`, `get_backend`, `list_backends`
- `MockInferenceBackend`: deterministic accept/reject; no tokens or GPU work
- Failure types: `BackendUnavailable`, `BackendTimeout`, `BackendRejected`, `BackendMisconfigured`, `BackendInternalFailure`
- Events: `backend_registered`, `backend_removed`, `backend_selected`, `batch_submitted`, `batch_accepted`, `batch_rejected`, `backend_health_changed`

## Not implemented

- vLLM, TGI, or Hugging Face SDK integration
- Token generation or streaming
- Worker routing or load-based backend selection
- Retry logic
- HTTP APIs
- Metrics backend export

## Contract operations

| Operation | Input | Output | Failure |
| --- | --- | --- | --- |
| `submit_batch` | `DispatchBatch` | `BatchSubmitResult` | `BackendUnavailable`, `BackendInternalFailure` |
| `get_request_status` | `request_id` | `RequestStatusResult` | `BackendMisconfigured` if backend missing |
| `cancel_request` | `request_id` | `CancelRequestResult` | same |
| `health_check` | — | `HealthCheckResult` | backend-defined |
| `backend_metadata` | — | `BackendMetadata` | backend-defined |

## Failure propagation

| Type | When | Propagation |
| --- | --- | --- |
| `BackendUnavailable` | Backend missing or unhealthy | Raised to scheduler caller |
| `BackendTimeout` | Reserved for future timeout handling | Not emitted yet |
| `BackendRejected` | Backend returns `accepted=false` | `BatchSubmitResult.reason`; `batch_rejected` event |
| `BackendMisconfigured` | Unknown `backend_id` | Raised at submit |
| `BackendInternalFailure` | Unexpected backend exception | Raised at submit |

No automatic retries in Session 10.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `INFERENCE_ADAPTER_DEFAULT_BACKEND_ID` | `mock` | Default backend for submit |
| `INFERENCE_ADAPTER_REGISTER_MOCK_BACKEND` | `true` | Register mock on startup |

## Embedded wiring

```python
from inference_adapter import create_application
from scheduler.integrations.embedded_adapter import EmbeddedAdapterClient

adapter = create_application()
await adapter.startup()

client = EmbeddedAdapterClient(adapter)
# pass client to scheduler.create_application(..., adapter_client=client)
```

## Scheduler integration

Scheduler `BatchDispatchService` builds `common_schemas.batch.Batch` from
scheduler batch membership and calls `AdapterClient.submit_batch()`. The adapter
forwards to the registered backend. Mock backend returns `mock_acknowledged`.

## Type naming

- `inference_adapter.backend.state.BackendState` — adapter process health (Session 10)
- `common_schemas.states.BackendState` — worker membership lifecycle (future control plane)

## Layout

```
src/inference_adapter/
  backend/contract.py     InferenceBackend protocol
  backend/state.py        BackendState + transitions
  backend/models.py         submit/status/metadata types
  backend/failures.py       failure taxonomy
  registry/registry.py      registration only
  backends/mock.py          mock implementation
  application.py            adapter lifecycle
  observability/events.py
```
