# Streaming Runtime

**Status:** Implemented (Session 19)  
**Owner:** api-gateway (transport, stream engine), inference-adapter (backend streaming bridge), gpu_inference_observability (models, events, metrics)

## Scope

This document describes the implemented streaming path from inference backend to HTTP client. It does not cover multi-node streaming, autoscaling, or benchmarking.

## Architecture

```
Client
  ↓ HTTP SSE (text/event-stream)
API Gateway (StreamEngine, sse.py)
  ↓ StreamChunk
RequestPathOrchestrator.execute_streaming_path
  ↓ queue → schedule → batch → submit (ack)
Inference Adapter (stream_inference_request bridge)
  ↓ backend.stream_request()
vLLM or Mock backend
```

The gateway does not call vLLM APIs directly. Token generation is owned by the backend; token delivery to the client is owned by `StreamEngine`.

## Domain Models

Location: `packages/observability/src/gpu_inference_observability/streaming/models.py`

| Type | Role |
|------|------|
| `StreamSession` | Per-request streaming state, timing, generated text |
| `StreamChunk` | Backend-agnostic token delta |
| `StreamContext` | request_id, stream_id, backend_id, batch_id, timestamps |
| `StreamResult` | Terminal snapshot including TTFT and ITL aggregates |
| `StreamLifecycleState` | Stream-level lifecycle (see below) |

Metrics persistence uses `StreamingMetricsRecord` in `packages/common-schemas/src/common_schemas/streaming.py`.

## Request Lifecycle

Request lifecycle (`RequestState`) and stream lifecycle (`StreamLifecycleState`) are separate.

**Request path (streaming):**

`RECEIVED → VALIDATED → ADMITTED → QUEUED → SCHEDULED → BATCHED → SUBMITTED → STREAMING → COMPLETED`

For streaming requests, `IntegratedPlatformClient.accept_request()` stops at `QUEUED`. Execution continues inside `StreamEngine.stream_sse()`.

**Stream lifecycle:**

| State | Meaning |
|-------|---------|
| `STREAM_CREATED` | SSE session started, no tokens yet |
| `STREAM_ACTIVE` | First token emitted |
| `STREAM_COMPLETED` | Finish reason received, `[DONE]` sent |
| `STREAM_CANCELLED` | Client disconnect or explicit cancellation |
| `STREAM_FAILED` | Backend or orchestrator error |

## SSE Transport

Location: `services/api-gateway/src/api_gateway/streaming/sse.py`

- `Content-Type: text/event-stream`
- Each event: `data: <json>\n\n`
- Termination: `data: [DONE]\n\n`
- Chunk object: `chat.completion.chunk` with `choices[0].delta.content`

**OpenAI deviations:**

- Error chunks include a top-level `error` string field in addition to `finish_reason: "error"`.
- Response headers include `X-Stream-Id` (platform-specific).
- Role delta is sent on the first content chunk when present.

## TTFT Model

Measured fields on `StreamTimingMeasurements`:

- `request_received_time` — set when `StreamSession` is created at gateway receive
- `first_token_time` — set on first token delta
- `completion_time` — set on stream completion, cancellation, or failure

`ttft_ms = first_token_time - request_received_time`

Values are stored on `RegisteredRequest.stream_metrics` and in execution records. No performance claims are made from these measurements.

## ITL Model

Each token delta records a timestamp in `token_timestamps`. Inter-token latency samples are consecutive deltas in milliseconds.

Aggregates persisted:

- `itl_ms_p50`
- `itl_ms_p99`

Individual samples are available on `StreamResult.itl_ms_samples` at runtime but are not persisted separately.

Prometheus histogram: `gpu_inference_request_itl_seconds` (recorded per token interval).

## Failure Handling

| Condition | Behavior |
|-----------|----------|
| Client disconnect | `disconnect_check` returns true → cancel backend stream → `RequestState.CANCELLED` → partial metrics persisted |
| Explicit cancellation | `StreamEngine.cancel_stream(stream_id)` — same as disconnect |
| Backend stream failure | Exception propagated → `STREAM_FAILED` → error SSE chunk → `RequestState.FAILED` |
| Queue/scheduler failure | Raised before streaming starts; no SSE body beyond error |

## Observability

**Structured log + trace events** (`StreamEventEmitter`):

- `stream_created`
- `first_token_emitted`
- `token_emitted`
- `stream_completed`
- `stream_failed`
- `stream_cancelled`

Each event includes `request_id`, `stream_id`, and timestamp.

**Prometheus counters:**

- `gpu_inference_streams_created_total`
- `gpu_inference_streams_completed_total`
- `gpu_inference_streams_failed_total`
- `gpu_inference_streams_cancelled_total`

**Histograms:**

- `gpu_inference_request_ttft_seconds`
- `gpu_inference_request_itl_seconds`

## Validation

`runtime-validation/stream_validation.py` covers:

- Successful streaming (mock backend)
- Stream cancellation
- Backend stream failure injection
- Client disconnect simulation

Run: `python runtime-validation/stream_validation.py`

## Limitations

- Streaming requires `full_path_integrated=true` on the gateway.
- Non-integrated control plane mode returns validation error for `stream=true`.
- vLLM batch dispatch defers inference when `stream=true`; tokens come only from `stream_request`.
- No request-level streaming timeout beyond existing queue/backend timeouts.
- Replay of streaming requests re-executes the path; token timing will differ.
- Multi-request batch streaming is not supported; one stream per request.

## Planned / Not Implemented

- Multi-node stream routing
- Autoscaling based on stream load
- Benchmarking harness for TTFT/ITL
- Kubernetes-specific streaming ingress configuration
