# vLLM Local Runtime

**Status:** Session 18 configuration reference. Requires a running vLLM OpenAI-compatible server.

**Not implemented:** Kubernetes deployment, multi-node serving, autoscaling.

## Requirements

- Python environment with platform dependencies installed
- vLLM installed in a separate environment or container
- GPU with sufficient memory for selected model (operator responsibility)
- Model weights accessible to vLLM

## Start vLLM

Example (model and GPU settings are operator choices, not hardcoded):

```bash
python -m vllm.entrypoints.openai.api_server \
  --model "${VLLM_MODEL}" \
  --host 127.0.0.1 \
  --port 8000 \
  --tensor-parallel-size "${VLLM_TENSOR_PARALLEL_SIZE:-1}" \
  --gpu-memory-utilization "${VLLM_GPU_MEMORY_UTILIZATION:-0.9}"
```

Verify:

```bash
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/v1/models
```

## Platform configuration

Environment variables for embedded stack:

| Variable | Default | Purpose |
| --- | --- | --- |
| `INFERENCE_ADAPTER_REGISTER_MOCK_BACKEND` | `true` | Set `false` to disable mock |
| `INFERENCE_ADAPTER_REGISTER_VLLM_BACKEND` | `false` | Set `true` to register vLLM |
| `INFERENCE_ADAPTER_DEFAULT_BACKEND_ID` | `mock` | Set `vllm` when using vLLM |
| `INFERENCE_ADAPTER_VLLM_BASE_URL` | `http://127.0.0.1:8000` | vLLM server URL |
| `INFERENCE_ADAPTER_VLLM_MODEL` | empty | Default model ID |
| `INFERENCE_ADAPTER_VLLM_SUPPORTED_MODELS` | empty | Comma-separated allowlist; falls back to `VLLM_MODEL` |
| `INFERENCE_ADAPTER_VLLM_MAX_BATCH_SIZE` | `8` | Max assignments per batch |
| `INFERENCE_ADAPTER_VLLM_REQUEST_TIMEOUT_SECONDS` | `120` | Inference HTTP timeout |
| `INFERENCE_ADAPTER_VLLM_HEALTH_TIMEOUT_SECONDS` | `5` | Health probe timeout |
| `INFERENCE_ADAPTER_VLLM_TENSOR_PARALLEL_SIZE` | unset | Reported in backend metadata only |
| `INFERENCE_ADAPTER_VLLM_GPU_MEMORY_UTILIZATION` | unset | Reported in backend metadata only |
| `SCHEDULER_DEFAULT_BACKEND_ID` | `mock` | Must match adapter default when dispatching |

Example:

```bash
export INFERENCE_ADAPTER_REGISTER_MOCK_BACKEND=false
export INFERENCE_ADAPTER_REGISTER_VLLM_BACKEND=true
export INFERENCE_ADAPTER_DEFAULT_BACKEND_ID=vllm
export INFERENCE_ADAPTER_VLLM_MODEL="${VLLM_MODEL}"
export SCHEDULER_DEFAULT_BACKEND_ID=vllm
```

## Limitations

- Sequential per-assignment execution inside `submit_batch` (no vLLM continuous batching integration in Session 18)
- Single vLLM server URL; no multi-node routing
- No streaming responses
- Health state `degraded` when server is up but configured model is not loaded

## Documentation

[docs/architecture/vllm-integration.md](../docs/architecture/vllm-integration.md)
