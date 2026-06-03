# API Gateway

Status: Session 11 — full embedded request path through mock backend
Implementation: HTTP server; lifecycle completes at COMPLETED; no model tokens

## Ownership

Process: `services/api-gateway`. Package: `api_gateway`.

Orchestrates validation and embeds control plane, scheduler, and inference adapter
when `GATEWAY_FULL_PATH_INTEGRATED=true` (default).

## Responsibilities (implemented)

- OpenAI-compatible HTTP (`POST /v1/chat/completions`, `POST /v1/completions`)
- Bearer API key validation, body size and schema validation
- Full embedded path: gateway → control plane → queue → scheduler → batch → adapter → mock
- Lifecycle through `COMPLETED` on success
- Trace propagation: `request_id`, `correlation_id`, `batch_id`, `backend_id`
- Correlation headers (`X-Correlation-Id`, `X-Request-Id`)
- Structured logging and request timing middleware
- `GET /health`, `GET /ready`, `GET /version`

## Responsibilities (not implemented)

- Real model completions or token generation
- Streaming (`stream=true` returns HTTP 501)
- Separate-process service HTTP (in-process only)
- vLLM, GPU execution, routing
- Prometheus export, rate limiting

## Request flow (Session 11)

```
POST /v1/chat/completions
  → validate + SubmitRequest
  → RequestPathOrchestrator.execute_full_path()
  → COMPLETED (or REJECTED / FAILED)
  → placeholder JSON response
```

See `docs/workflows/end-to-end-request-execution.md`.

## Run locally

```bash
pip install -e packages/common-schemas -e packages/observability \
  -e services/control-plane -e services/scheduler \
  -e services/inference-adapter -e services/api-gateway

GATEWAY_API_KEYS=dev-key gpu-inference-gateway
```

```bash
curl -s -H "Authorization: Bearer dev-key" -H "Content-Type: application/json" \
  -d '{"model":"demo","messages":[{"role":"user","content":"hello"}]}' \
  http://localhost:8080/v1/chat/completions
```

Response includes `lifecycle_state=completed`.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `GATEWAY_API_KEYS` | empty | Comma-separated allowlist |
| `GATEWAY_FULL_PATH_INTEGRATED` | true | Embed CP + scheduler + adapter |
| `GATEWAY_CONTROL_PLANE_INTEGRATED` | true | Used when full path disabled |

## Layout

```
src/api_gateway/
  runtime/
    stack.py                 PlatformStack wiring
    orchestrator.py          full path execution
    integrated_client.py     ControlPlaneClient for Session 11
  pipeline.py
  dependencies.py
```

## Validation

```bash
python tests/integration/session11_scenarios.py
```
