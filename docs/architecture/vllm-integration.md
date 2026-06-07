# vLLM Integration

**Status:** Implemented (Session 18). `VLLMBackend` executes inference via vLLM OpenAI-compatible HTTP API.

**Not implemented:** Benchmarking, autoscaling, Kubernetes deployment, multi-node serving, streaming, vLLM continuous batching integration.

## Architecture

```
Scheduler BatchDispatchService
        │
        ▼
InferenceAdapterApplication.submit_batch()
        │
        ▼
VLLMBackend.submit_batch()
        │
        ▼
POST /v1/chat/completions  (vLLM server)
        │
        ▼
RequestCompletionResult → InferenceCompletionRecord
        │
        ▼
LifecycleManager.complete_request(completion=...)
```

The scheduler and batch engine remain backend-agnostic. They dispatch `common_schemas.batch.Batch` to the adapter. vLLM-specific logic is isolated in `inference_adapter.backends.vllm`.

## Ownership

| Component | Module | Responsibility |
| --- | --- | --- |
| `InferenceBackend` protocol | `inference_adapter.backend.contract` | Backend interface |
| `VLLMBackend` | `inference_adapter.backends.vllm` | HTTP client, inference execution, health probes |
| `VLLMBackendConfig` | `inference_adapter.backends.vllm` | URL, model, timeouts, GPU metadata |
| `InferenceCompletionRecord` | `common_schemas.completion` | Cross-boundary completion payload |
| Adapter wiring | `inference_adapter.application` | Registration, health refresh, token metrics |
| Completion attach | `control_plane.lifecycle.manager` | `complete_request(completion=...)` |
| Orchestrator fetch | `api_gateway.runtime.orchestrator` | Reads completion after SUBMITTED |
| Gateway response | `api_gateway.pipeline` | Returns generated text and token usage |

## VLLMBackend

Implements `InferenceBackend`:

| Method | Behavior |
| --- | --- |
| `submit_batch` | Validates model and batch size; runs health check; executes each assignment via `/v1/chat/completions`; returns `BatchSubmitResult` with `completions` |
| `get_request_status` | In-memory status from last submission |
| `get_request_completion` | Returns stored `RequestCompletionResult` |
| `cancel_request` | Marks request cancelled in memory |
| `health_check` | `GET /health` and `GET /v1/models`; states: `healthy`, `degraded`, `unavailable` |
| `backend_metadata` | `backend_type=vllm`, supported models, loaded models, base URL |

### Error handling

| Condition | Behavior |
| --- | --- |
| Server unreachable | `BackendUnavailable` on submit; health `unavailable` |
| HTTP timeout | `BackendTimeout` |
| HTTP 5xx | `BackendInternalFailure` |
| HTTP 4xx on completion | Assignment marked failed; batch rejected |
| Model not loaded | Health `degraded`; submit returns `accepted=False, reason=model_not_loaded` |
| Unsupported model | `accepted=False, reason=unsupported_model` |

Lifecycle, trace events, and persistence follow existing failure paths via orchestrator `mark_failed`.

## Completion Handling

On successful inference:

1. `VLLMBackend` stores `RequestCompletionResult` per request ID
2. `InferenceAdapterApplication.submit_batch` records token metrics
3. Orchestrator transitions to `SUBMITTED`, calls `adapter.get_request_completion`
4. `LifecycleManager.complete_request(completion=...)` attaches `InferenceCompletionRecord` to registry entry
5. Lifecycle event `request_completed` includes token counts in `extra`
6. Execution record capture stores `completion` on `RequestExecutionRecord`
7. Gateway `placeholder_chat_response` returns generated text when completion is present

Mock backend behavior is unchanged: no completion record; gateway returns placeholder text.

## Backend Health

On adapter `startup()`, `refresh_backend_health()` runs for each registered backend.

| Health state | Adapter `BackendState` |
| --- | --- |
| `healthy` | `HEALTHY` |
| `degraded` | `DEGRADED` |
| `unavailable` | `UNHEALTHY` |

`submit_batch` rejects when registry state is `UNHEALTHY` or `STOPPED`.

## Metrics

Recorded via existing `RuntimeMetricsRecorder`:

| Metric | When |
| --- | --- |
| `gpu_inference_backend_submissions_total` | Before backend call |
| `gpu_inference_backend_acceptance_total` | Batch accepted |
| `gpu_inference_backend_failures_total` | Exception during submit |
| `gpu_inference_backend_request_duration_seconds` | Submit call duration |
| `gpu_inference_backend_prompt_tokens_total` | Per completion prompt tokens |
| `gpu_inference_backend_completion_tokens_total` | Per completion completion tokens |

No throughput or latency claims are made beyond counter/histogram observation.

## Configuration

See [infra/vllm/README.md](../../infra/vllm/README.md).

Registration flags:

- `INFERENCE_ADAPTER_REGISTER_VLLM_BACKEND=true`
- `INFERENCE_ADAPTER_REGISTER_MOCK_BACKEND=false`
- `INFERENCE_ADAPTER_DEFAULT_BACKEND_ID=vllm`

Programmatic registration (validation/tests):

```python
adapter.register_backend(VLLMBackend(VLLMBackendConfig.from_values(...)))
```

## Validation

```bash
python runtime-validation/vllm_validation.py
```

Uses `httpx.MockTransport` for deterministic scenarios:

1. Successful completion with token metrics
2. Model load failure (`degraded` health)
3. Backend unavailable
4. Inference timeout

Optional real vLLM execution: start vLLM per `infra/vllm/README.md`, set env vars, submit via embedded stack.

## Limitations

- Assignments executed sequentially within one batch
- In-memory completion store; not shared across processes
- No streaming
- No vLLM engine lifecycle management (start/stop) in platform code
- GPU settings are passed to metadata only; vLLM server owns GPU allocation
- Replay of vLLM completions re-executes inference on replay stack

## Related docs

- Runtime persistence: [runtime-persistence.md](./runtime-persistence.md)
- End-to-end workflow: [../workflows/end-to-end-request-execution.md](../workflows/end-to-end-request-execution.md)
