# System Overview

Status: Architecture Phase
Implementation: Not Started

This document describes the intended high-level structure of the platform. It is
a design target, not a description of running software.

## Purpose

Provide predictable LLM serving on GPU hardware. Clients send OpenAI-compatible
requests; the platform admits, queues, schedules, and runs them on inference
workers, returning streamed or complete responses.

## Components and responsibilities

- API gateway (`services/api-gateway`): terminates client HTTP, validates
  requests against schemas, handles streaming and cancellation, forwards work to
  the scheduler. Holds no scheduling logic.
- Control plane (`services/control-plane`): owns the model registry, routing
  policy, worker pool membership, and runtime configuration. Answers "which
  model and which pool" questions.
- Scheduler (`services/scheduler`): admission control, queue, batching, and
  dispatch. The only component that assigns work to workers.
- Inference adapter (`services/inference-adapter`): translates platform-internal
  requests into calls to a concrete inference backend and normalizes responses.
- Metrics collector (`services/metrics-collector`): receives and aggregates
  metrics and traces, exposes them for Prometheus and Grafana.
- Operator console (`services/operator-console`): read-only operational view of
  queues, workers, and recent requests for debugging.

## Shared packages

- `packages/common-schemas`: request, response, and internal message contracts.
  The single source of truth for cross-service data shapes.
- `packages/observability`: shared logging, metrics, and tracing helpers so all
  services emit consistent signals.

## Request path (summary)

Client -> API gateway -> Scheduler (admission, queue, batch) -> Inference
adapter -> Worker -> stream back through gateway to client. The control plane
informs routing; the metrics collector observes every stage. The detailed path
is in `docs/workflows/request-serving-workflow.md`.

## Boundaries

Services communicate over network APIs using schemas from `common-schemas`. No
service imports another service's internal modules. The gateway never calls
workers directly; the scheduler is the only path to a worker.

## Out of scope for this document

Backend-specific integration, concrete batching algorithms, and storage choices
are covered in `runtime-model.md`, `scheduler-design.md`, and `storage-design.md`.
