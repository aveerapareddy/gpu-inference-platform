# OpenAI-Compatible API Contracts

Status: Architecture Phase (Session 2 — contracts locked)
Implementation: Not Started

Machine-readable spec: `api-specs/openapi.yaml`.

These endpoints are planned. No server listens yet.

## Authentication

All inference endpoints require:

```
Authorization: Bearer <api_key>
```

Missing or invalid key: HTTP 401, `error.type` = `authentication_error`.

## POST /v1/chat/completions

Primary client surface. Maps to internal `InferenceRequest` after validation.

### Request schema (v1 supported)

| Field | Type | Required | Validation |
| --- | --- | --- | --- |
| `model` | string | yes | Must exist in control-plane registry |
| `messages` | array | yes | 1–128 items; each item has `role`, `content` |
| `messages[].role` | enum | yes | `system`, `user`, `assistant` |
| `messages[].content` | string | yes | Max length from model config (default 32768 chars total across messages) |
| `stream` | boolean | no | Default `false` |
| `max_tokens` | integer | no | Default from model config; max from model `max_output_tokens` |
| `temperature` | number | no | 0.0–2.0; default 1.0 |
| `top_p` | number | no | 0.0–1.0; default 1.0 |

### Request schema (v1 excluded)

Rejected with HTTP 400, `error.type` = `unsupported_field` if present:

| Field | Reason |
| --- | --- |
| `tools`, `tool_choice` | No tool calling in v1 |
| `functions`, `function_call` | Deprecated OpenAI path; excluded |
| `response_format` | No structured output mode in v1 |
| `logprobs`, `top_logprobs` | Not exposed |
| `n` | Only `n=1`; other values rejected |
| `presence_penalty`, `frequency_penalty` | Backend may not support; excluded until adapter declares support |
| `seed` | Excluded until reproducibility is defined per backend |
| `user` | Optional metadata; excluded in v1 (no per-user routing) |
| `stream_options` | Excluded |
| `parallel_tool_calls` | Excluded |

### Non-streaming response (200)

| Field | Type | Notes |
| --- | --- | --- |
| `id` | string | Platform `request_id` exposed as completion id |
| `object` | string | Always `chat.completion` |
| `created` | integer | Unix seconds |
| `model` | string | Echo resolved model |
| `choices` | array | Length 1 in v1 |
| `choices[0].message.role` | string | `assistant` |
| `choices[0].message.content` | string | Full completion text |
| `choices[0].finish_reason` | enum | `stop`, `length`, `cancelled`, `error` |
| `usage.prompt_tokens` | integer | From backend when available; else estimated |
| `usage.completion_tokens` | integer | |
| `usage.total_tokens` | integer | |

### Streaming response (200)

`Content-Type: text/event-stream`

Each event:

```
data: <json chunk>\n\n
```

Chunk schema:

| Field | Type | Notes |
| --- | --- | --- |
| `id` | string | `request_id` |
| `object` | string | `chat.completion.chunk` |
| `created` | integer | Unix seconds |
| `model` | string | |
| `choices[0].delta.role` | string | Present on first chunk only |
| `choices[0].delta.content` | string | Token text; may be empty string |
| `choices[0].finish_reason` | string or null | Set on final chunk |
| `choices[0].index` | integer | Always 0 |

Termination:

```
data: [DONE]\n\n
```

### Error format (all endpoints)

HTTP 4xx/5xx with body:

```json
{
  "error": {
    "type": "queue_full",
    "message": "human-readable detail",
    "param": null,
    "code": "queue_full",
    "retry_after_ms": 250
  }
}
```

| Field | Required | Notes |
| --- | --- | --- |
| `type` | yes | Stable machine enum (see table below) |
| `message` | yes | Operator/client readable |
| `code` | yes | Duplicate of `type` for OpenAI client compatibility |
| `param` | no | JSON pointer to invalid field when validation error |
| `retry_after_ms` | no | Present for `queue_full`, `no_capacity` |

### Error types (v1)

| type | HTTP | Source |
| --- | --- | --- |
| `authentication_error` | 401 | Gateway |
| `validation_error` | 400 | Gateway |
| `unsupported_field` | 400 | Gateway |
| `unknown_model` | 404 | Gateway / control plane |
| `queue_full` | 429 | Scheduler admission |
| `no_capacity` | 503 | Scheduler admission |
| `queue_timeout` | 504 | Scheduler |
| `internal_error` | 500 | Any component |
| `worker_error` | 502 | Adapter / worker |

## POST /v1/completions

Legacy completions API. Supported in v1 for client compatibility with a subset
of fields.

### Request (v1 supported)

| Field | Type | Required | Validation |
| --- | --- | --- | --- |
| `model` | string | yes | Registry lookup |
| `prompt` | string | yes | Max length per model config |
| `stream` | boolean | no | Default `false` |
| `max_tokens` | integer | no | Same rules as chat |
| `temperature` | number | no | 0.0–2.0 |
| `top_p` | number | no | 0.0–1.0 |

Gateway converts to internal chat-shaped `InferenceRequest` (single user message
from `prompt`) before scheduler submit. Response uses `object: text_completion`.

### v1 excluded

Same exclusion policy as chat for penalties, `logprobs`, `n>1`, `suffix`, `echo`.

## GET /health

Liveness. Process is running.

| | |
| --- | --- |
| **Response** | 200 `{"status":"ok"}` |
| **Failure** | No response implies process down (orchestrator restarts) |
| **Owner** | Each service exposes its own `/health` |

## GET /ready

Readiness. Process can accept work.

| Service | Ready when |
| --- | --- |
| API gateway | Can reach scheduler and control plane (cached registry acceptable within staleness policy) |
| Scheduler | At least one healthy worker for default model pool, or explicit degrade mode documented |
| Control plane | Durable store reachable |
| Inference adapter | At least one registered backend worker |
| Metrics collector | N/A or always ready (observation only) |

| | |
| --- | --- |
| **Response** | 200 `{"status":"ready"}` or 503 `{"status":"not_ready","reason":"..."}` |
| **Owner** | Per service |

## GET /metrics

Prometheus text exposition format 0.0.4.

| | |
| --- | --- |
| **Response** | 200 `text/plain`; version=0.0.4 body |
| **Auth** | None on demo deployment; production deployments may add network policy |
| **Owner** | Each service scrapes its own; metrics collector aggregates platform-wide |

Metric names: `docs/contracts/observability-metrics.md`.

## Validation rules (gateway)

1. Content-Type must be `application/json` for POST bodies.
2. Body size max 4 MiB (configurable).
3. `model` required and non-empty.
4. Total prompt tokens estimated before admit; reject if over model `max_prompt_tokens`.
5. `stream` must be boolean if present.

## Limitations (v1)

- Single choice per request (`n=1`).
- No embeddings, images, audio, or fine-tune endpoints.
- No batch API file upload.
- Rate limiting per API key is planned; not in contract until gateway implements it.
