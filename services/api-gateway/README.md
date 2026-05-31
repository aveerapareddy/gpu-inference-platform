# API Gateway

Status: Session 4 — validation and contract enforcement implemented
Implementation: HTTP server runs; inference and scheduler not connected

## Ownership

Process: `services/api-gateway`. Package: `api_gateway`.

## Responsibilities (implemented)

- OpenAI-compatible HTTP surface (`POST /v1/chat/completions`, `POST /v1/completions`)
- Bearer API key validation
- JSON body size limit (default 4 MiB)
- Supported vs unsupported field enforcement
- Pydantic schema validation for allowed fields
- Model lookup via control plane interface (stub registry)
- `InferenceRequest` and `RequestContext` creation per request
- Correlation IDs (`X-Correlation-Id`, `X-Request-Id`, response headers)
- Structured JSON logging and request timing middleware
- Operational endpoints: `GET /health`, `GET /ready`, `GET /version`
- OpenAI-shaped error responses for all failure classes

## Responsibilities (not implemented)

- Scheduler submit or queueing
- Streaming (SSE); `stream=true` returns HTTP 501
- Inference execution and real completions
- Prometheus metrics export (`GET /metrics`)
- Distributed tracing export
- HTTP control plane client (stub only)
- Rate limiting

## Lifecycle (per request)

1. Middleware records wall time; passes correlation headers through.
2. Auth: validate `Authorization: Bearer`.
3. Parse JSON; reject oversize or malformed bodies.
4. Reject unsupported fields; validate allowed schema.
5. Reject `stream=true` (not implemented).
6. Resolve model via `ControlPlaneClient.get_model`.
7. Build `InferenceRequest` and `GatewayRequestContext` (`RequestContext` inside).
8. Return placeholder completion JSON (contract shape only).
9. Log validation and response timing.

States `received` / `validated` are implied; scheduler states are not entered.

## Inputs

- Client HTTP requests and headers
- Stub control plane model registry

## Outputs

- HTTP 200 placeholder completions (non-streaming only)
- HTTP 4xx/5xx structured `error` objects
- Response headers: `X-Request-Id`, `X-Correlation-Id`
- Structured logs to stderr

## Control plane interface

- `api_gateway.control_plane.client.ControlPlaneClient` (protocol)
- `api_gateway.control_plane.stub.StubControlPlaneClient` (default)

Registered stub models: `demo`, `example-model`.

## Run locally

```bash
pip install -e packages/common-schemas -e packages/observability -e services/api-gateway
GATEWAY_API_KEYS=dev-key gpu-inference-gateway
```

Example:

```bash
curl -s http://localhost:8080/health
curl -s -H "Authorization: Bearer dev-key" -H "Content-Type: application/json" \
  -d '{"model":"demo","messages":[{"role":"user","content":"hello"}]}' \
  http://localhost:8080/v1/chat/completions
```

## Configuration

Environment prefix `GATEWAY_`:

| Variable | Default | Purpose |
| --- | --- | --- |
| `HOST` | `0.0.0.0` | Bind address |
| `PORT` | `8080` | Bind port |
| `MAX_BODY_BYTES` | 4194304 | Max JSON body |
| `API_KEYS` | empty | Comma-separated allowlist; empty accepts any non-empty bearer |
| `CONTROL_PLANE_STUB_ENABLED` | `true` | Use in-process stub |

## Contracts

- `api-specs/openapi.yaml`
- `docs/contracts/openai-api.md`
- `packages/common-schemas`

## Layout

```
src/api_gateway/
  app.py              FastAPI factory, lifespan, routers
  main.py             uvicorn entry
  config.py           settings
  dependencies.py     DI
  errors.py           OpenAI error envelope
  validation.py       auth, body, model rules
  context.py          GatewayRequestContext
  pipeline.py         validate + placeholder response
  middleware.py       timing logs
  control_plane/      client protocol + stub
  routers/            health, completions
  schemas/            client request models
```
