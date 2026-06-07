# GPU Inference Platform

Status: Foundation through Session 18 — vLLM inference backend

## Engineering thesis

Serving large language models on GPUs is a systems problem, not a model problem.
The hard parts are admission control, queueing, batching, fair multi-model
routing, cancellation, and observability under load. This project builds that
serving layer with explicit boundaries and predictable failure behavior, and
documents the design before writing the runtime.

## What this project is

A model serving system for LLMs. It accepts OpenAI-compatible requests, applies
admission control and bounded queueing, schedules work onto GPU-backed workers
through a narrow backend adapter, and returns streamed or non-streamed responses.
It targets local and single-cluster deployment for demonstration.

## What this project is not

- Not a training or fine-tuning system.
- Not a model; it serves models produced elsewhere.
- Not an OpenAI proxy or wrapper; it does not forward to a hosted API.
- Not a CRUD app or dashboard product.
- Not a managed multi-region cloud service.

## Planned architecture areas

- OpenAI-compatible streaming API surface
- Request admission control and bounded queueing
- Request batching, then continuous batching
- Multi-model routing and worker pool membership
- Inference backend integration through a narrow adapter
- Serving observability: metrics, traces, dashboards
- Reproducible benchmarking
- Single-cluster Kubernetes deployment
- Operator debugging workflows

## Repository structure

```
docs/
  overview/        project constitution and end state
  architecture/    system, runtime, scheduler, storage, observability,
                   security, tradeoffs
  workflows/       end-to-end request serving workflow
  runbooks/        local operational runbook (planned procedures)
  diagrams/        architecture and workflow diagrams
  examples/        Pointers to contract docs
  contracts/       API, runtime, state, service, metrics contracts
api-specs/         OpenAPI (client HTTP)
services/
  api-gateway/      OpenAI-compatible HTTP surface
  control-plane/    registry, routing, membership, config
  scheduler/        admission, queue, batching, dispatch
  inference-adapter/ backend integration interface
  metrics-collector/ metrics and trace aggregation
  operator-console/  read-only operational view
packages/
  common-schemas/  JSON Schema + Pydantic models (common_schemas)
  observability/   logging, tracing, metric names
services/          each has pyproject.toml and src/ (no runtime logic)
infra/
  db/              control-plane state store setup
  docker/          container builds and local compose
  k8s/             single-cluster manifests
  prometheus/      scrape, retention, alert config
  grafana/         dashboards
benchmarks/
  load-tests/      reproducible load-test definitions
  results/         recorded benchmark outputs
```

## Current phase

Session 1–2 locked architecture and contracts. Session 3 implemented shared
Python packages (`common_schemas`, `gpu_inference_observability`) and service
skeletons. No request execution, scheduling, or HTTP serving yet.

Read order: `docs/overview/project-constitution.md` →
`docs/workflows/request-serving-workflow.md` → `packages/common-schemas/README.md`.

## Implementation status

| Area | Status |
| --- | --- |
| Architecture documents (Session 1) | Complete |
| Platform contracts (Session 2) | Complete |
| Shared schema package (Session 3) | Complete |
| Observability package (Session 3) | Complete (scaffolding) |
| Runtime observability (Session 12) | Complete — trace store, events, timing, metrics models, snapshots (in-memory) |
| Runtime metrics export (Session 13) | Complete — centralized registry, Prometheus `/metrics` on gateway |
| OpenTelemetry tracing (Session 14) | Complete — span hierarchy, propagation, pluggable exporters |
| Failure injection and validation (Session 15) | Complete — deterministic injection, runtime-validation harness |
| Replay and debugging (Session 16) | Complete — execution records, replay engine, reconstruction, comparison (in-memory) |
| Runtime persistence (Session 17) | Complete — SQLite repository layer, restart recovery, durable execution history |
| vLLM inference backend (Session 18) | Complete — real model execution via OpenAI-compatible vLLM adapter |
| Service scaffolds (Session 3) | Complete |
| API gateway runtime | Session 14 — integrated path with OpenTelemetry root span |
| Control plane runtime | Session 12 — lifecycle/queue events recorded to trace store |
| Scheduler runtime | Session 12 — scheduler/batch events recorded to trace store |
| Inference adapter runtime | Session 12 — per-request backend events recorded |
| Metrics collector runtime | Not started |
| Operator console | Not started |
| Infra (db, docker, k8s) | Not started |
| Observability stack (prometheus, grafana) | Session 13 — Prometheus export only; Grafana not started |
| Benchmarks | Not started |

This table is the source of truth for what exists. It is updated in the same
change that adds or removes a capability.

## Non-goals

- No model training or fine-tuning.
- No multi-region or multi-cluster orchestration.
- No billing, accounts, or user-management product surface.
- No proprietary model weights in the repository.
- No autoscaling controller in the first complete version.
- No content moderation or safety classification.

## Next milestone

Begin the Serving Phase: working API gateway, scheduler, and inference adapter
for a single model through a mock or CPU backend, with the request path
observable per `docs/workflows/request-serving-workflow.md`. Exit criteria in
`docs/overview/project-end-state.md`.
