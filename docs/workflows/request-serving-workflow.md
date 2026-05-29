# Request Serving Workflow

Status: Architecture Phase
Implementation: Not Started

This document describes the intended end-to-end path of a single inference
request. It is a design target. No part of this path is implemented yet.

## Actors

- Client: sends an OpenAI-compatible chat completion request.
- API gateway: validates and relays the request and its response stream.
- Control plane: resolves model and worker pool.
- Scheduler: admission, queue, batch, dispatch.
- Inference adapter and worker: run the model.
- Metrics collector: observes every stage.

## Happy path (streaming)

1. Client sends `POST /v1/chat/completions` with `stream: true` and a bearer
   token.
2. Gateway authenticates the key and validates the body against the request
   schema. Invalid requests are rejected here with a typed error.
3. Gateway resolves the target model with the control plane.
4. Gateway submits the request to the scheduler.
5. Scheduler runs admission control:
   - Accept: enqueue in the model's queue.
   - Reject: return a typed error with a retry hint; the gateway maps it to an
     HTTP response.
6. Scheduler batches compatible queued requests and dispatches a batch to a
   worker within capacity.
7. Worker streams tokens back through the adapter and scheduler to the gateway.
8. Gateway relays tokens to the client as server-sent events until completion.
9. Each stage emits metrics and a trace span tied to the request identifier.

## Non-streaming path

Identical through dispatch. The gateway collects the worker's stream to
completion and returns a single response body instead of incremental events.

## Cancellation path

- Client disconnects or sends a cancel.
- Gateway detects the closed connection and signals the scheduler.
- Scheduler removes the request if still queued, or signals the worker to stop if
  in flight.
- Freed capacity is returned to the dispatch loop.

## Rejection reasons (typed)

- Validation failure: malformed or disallowed request.
- Unknown or unavailable model.
- Queue full: admission limit reached.
- No available worker for the model.
- Upstream worker failure during execution.

Each reason maps to a stable error code and an HTTP status, and increments a
labeled metric.

## Observability of the path

A single request can be followed end to end by its request identifier across
gateway, scheduler, and worker spans, with per-stage latency available in
metrics. Details are in `docs/architecture/observability-and-reliability.md`.
