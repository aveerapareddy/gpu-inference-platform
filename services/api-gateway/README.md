# API Gateway

Status: Session 6 — integrated with control plane through QUEUED
Implementation: HTTP server runs; requests registered and queued; no inference

## Ownership

Process: `services/api-gateway`. Package: `api_gateway`.

## Responsibilities (implemented)

- OpenAI-compatible HTTP (`POST /v1/chat/completions`, `POST /v1/completions`)
- Bearer API key validation, body size and schema validation
- Unsupported field rejection
- Model lookup (stub registry: `demo`, `example-model`)
- `RequestContext` and `InferenceRequest` construction
- Handoff to embedded control plane: lifecycle through `QUEUED`
- Correlation headers (`X-Correlation-Id`, `X-Request-Id`)
- Structured logging and request timing middleware
- `GET /health`, `GET /ready`, `GET /version`
- OpenAI-shaped errors including admission rejections from control plane

## Responsibilities (not implemented)

- Scheduler submit or inference execution
- Streaming (`stream=true` returns HTTP 501)
- Real model completions (placeholder JSON only)
- HTTP to separate control-plane process (in-process integration only)
- Prometheus metrics, distributed tracing export
- Rate limiting

## Request flow (Session 6)

```
Client POST
  → Gateway: auth, parse, validate
  → Gateway: build SubmitRequest + RequestContext
  → Control Plane: RECEIVED → VALIDATED → ADMITTED → QUEUED
  → Gateway: placeholder completion response
```

Admission rejections return HTTP 429/400 with structured `error` body.
Internal control plane errors return HTTP 500 and `FAILED` in registry when possible.

## Run locally

```bash
pip install -e packages/common-schemas -e packages/observability \
  -e services/control-plane -e services/api-gateway
GATEWAY_API_KEYS=dev-key gpu-inference-gateway
```

```bash
curl -s -H "Authorization: Bearer dev-key" -H "Content-Type: application/json" \
  -d '{"model":"demo","messages":[{"role":"user","content":"hello"}]}' \
  http://localhost:8080/v1/chat/completions
```

Response message includes `lifecycle_state=queued`.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `GATEWAY_API_KEYS` | empty | Comma-separated allowlist |
| `GATEWAY_CONTROL_PLANE_INTEGRATED` | true | Embed control plane in gateway process |

## Contracts

- `api-specs/openapi.yaml`
- `docs/contracts/openai-api.md`
- `docs/workflows/request-serving-workflow.md`

## Layout

```
src/api_gateway/
  app.py
  pipeline.py              validate + control plane handoff
  control_plane/
    integrated.py          IntegratedControlPlaneClient
    client.py              protocol
  routers/                 health, completions
```
