# Project Constitution

Status: Architecture Phase
Implementation: Not Started

This document defines the rules the project must follow. It takes precedence
over any individual design document. If a design decision conflicts with this
document, this document wins until it is explicitly amended.

## What the system is

GPU Inference Platform is a model serving system for large language models. It
accepts inference requests over an OpenAI-compatible HTTP API, applies admission
control and queueing, schedules work onto GPU-backed inference workers, and
returns streamed or non-streamed responses.

The platform sits between clients and one or more inference backends. Its job is
to make GPU serving predictable under load: bounded latency, bounded queue
depth, fair access across models and tenants, and clear operational signals when
the system is saturated.

## What the system is not

- It is not a training system. No fine-tuning, no gradient computation.
- It is not a model. It serves models produced elsewhere.
- It is not an OpenAI proxy. It does not forward requests to a hosted API.
- It is not a general web application or dashboard product.
- It is not a managed cloud service. It targets local and single-cluster
  deployment for demonstration.

## Non-negotiable architecture rules

1. Every request passes through admission control before it reaches a GPU. No
   request bypasses the queue.
2. The scheduler is the single authority for what runs on a worker. Services do
   not call workers directly.
3. Backpressure is explicit. When the system is full it rejects with a typed
   error and a retry signal, it does not silently buffer without bound.
4. Service boundaries communicate through versioned schemas in
   `packages/common-schemas`. No service reaches into another service's
   internals.
5. State that must survive a restart lives in a defined store. In-memory state
   is treated as disposable.
6. Streaming is a first-class path, not an add-on. Cancellation must propagate
   from client to worker.

## Reliability expectations

- A single worker failure must not take down the control plane or drop the whole
  queue.
- Every rejection and failure has a typed reason that is visible in metrics and
  logs.
- Queue depth, admission decisions, and per-request latency are observable at
  all times.
- The system degrades by shedding load, not by increasing unbounded latency.

These are target behaviors for the implemented system. None are claimed as
achieved during the Architecture Phase.

## Documentation rules

- Documents state current status at the top: phase and implementation state.
- Planned behavior and implemented behavior are kept clearly separate. A document
  must not describe planned behavior as if it exists.
- No benchmark numbers, latency claims, or throughput claims appear until they
  are produced by reproducible runs in `benchmarks/`.
- Plain, technical language. No marketing terms, no hype, no decorative
  formatting.

## Implementation enforcement rules

- No runtime code is added until the architecture documents for the affected
  area exist and are reviewed.
- A component is described as "implemented" only when it runs and is exercised by
  a test or runbook. Otherwise it is "planned" or "in progress".
- The README implementation status table is the source of truth for what exists.
  It is updated in the same change that adds or removes a capability.
