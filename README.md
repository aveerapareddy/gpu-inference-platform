# GPU Inference Platform

Status: Architecture Phase
Implementation: Not Started
Current Milestone: Repository skeleton and architecture foundation

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
  examples/        OpenAI-compatible request and response contracts
services/
  api-gateway/      OpenAI-compatible HTTP surface
  control-plane/    registry, routing, membership, config
  scheduler/        admission, queue, batching, dispatch
  inference-adapter/ backend integration interface
  metrics-collector/ metrics and trace aggregation
  operator-console/  read-only operational view
packages/
  common-schemas/  cross-service data contracts
  observability/   shared logging, metrics, tracing helpers
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

Architecture Phase. The repository contains the directory skeleton and the
architecture documents. No runtime logic is implemented. The design is fixed
first so that implementation follows a reviewed plan.

Start with `docs/overview/project-constitution.md` and
`docs/overview/project-end-state.md`, then the documents in `docs/architecture`.

## Implementation status

| Area | Status |
| --- | --- |
| Architecture documents | In progress |
| API gateway | Not started |
| Control plane | Not started |
| Scheduler | Not started |
| Inference adapter | Not started |
| Metrics collector | Not started |
| Operator console | Not started |
| Shared packages | Not started |
| Infra (db, docker, k8s) | Not started |
| Observability stack (prometheus, grafana) | Not started |
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

Complete and review the architecture documents, then begin the Serving Phase: a
working API gateway, scheduler, and inference adapter serving a single model
through a mock or CPU backend, with the request path observable. Scope and exit
criteria are defined in `docs/overview/project-end-state.md`.
