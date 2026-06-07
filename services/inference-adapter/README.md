# Inference Adapter

Status: Session 18 — vLLM backend for real inference execution; mock backend remains default

## Ownership

Process: `services/inference-adapter`. Package: `inference_adapter`.

The adapter owns the boundary between the scheduler and inference engines.
It registers backends, accepts dispatch batches, and maps failures to a
shared vocabulary. It does not schedule, queue, or serve HTTP to clients.

## Implemented

- `InferenceBackend` contract: `submit_batch`, `get_request_status`, `cancel_request`, `health_check`, `backend_metadata`
- `MockInferenceBackend`: deterministic accept/reject; no tokens or GPU work
- `VLLMBackend`: OpenAI-compatible HTTP client; executes `/v1/chat/completions`; stores completions
- `InferenceCompletionRecord` propagation via adapter → orchestrator → lifecycle
- Backend health refresh on adapter startup (`healthy`, `degraded`, `unavailable`)
- Token metrics: `backend_prompt_tokens_total`, `backend_completion_tokens_total`
- Failure types: `BackendUnavailable`, `BackendTimeout`, `BackendRejected`, `BackendMisconfigured`, `BackendInternalFailure`

## Not implemented

- TGI or Hugging Face SDK integration
- Streaming responses
- vLLM continuous batching integration
- Worker routing or load-based backend selection
- Retry logic
- HTTP APIs on adapter process

## vLLM configuration

See [infra/vllm/README.md](../../infra/vllm/README.md) and [docs/architecture/vllm-integration.md](../../docs/architecture/vllm-integration.md).

```bash
export INFERENCE_ADAPTER_REGISTER_MOCK_BACKEND=false
export INFERENCE_ADAPTER_REGISTER_VLLM_BACKEND=true
export INFERENCE_ADAPTER_DEFAULT_BACKEND_ID=vllm
export INFERENCE_ADAPTER_VLLM_MODEL="${VLLM_MODEL}"
export SCHEDULER_DEFAULT_BACKEND_ID=vllm
```

## Validation

```bash
python runtime-validation/vllm_validation.py
```

## Contract operations

| Operation | Input | Output | Failure |
| --- | --- | --- | --- |
| `submit_batch` | `DispatchBatch` | `BatchSubmitResult` (+ optional `completions`) | `BackendUnavailable`, `BackendInternalFailure`, `BackendTimeout` |
| `get_request_status` | `request_id` | `RequestStatusResult` | `BackendMisconfigured` if backend missing |
| `get_request_completion` | `request_id` | `InferenceCompletionRecord` or `None` | adapter-only extension |
| `cancel_request` | `request_id` | `CancelRequestResult` | same |
| `health_check` | — | `HealthCheckResult` | backend-defined |
| `backend_metadata` | — | `BackendMetadata` | backend-defined |
