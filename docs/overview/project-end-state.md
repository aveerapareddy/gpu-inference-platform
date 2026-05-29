# Project End State

Status: Architecture Phase
Implementation: Not Started

This document defines what "done" means for the project. It describes the target
system so that scope is bounded and progress is measurable. Nothing here is
claimed as built.

## What complete means

The project is complete when a client can send an OpenAI-compatible chat
completion request, streamed or non-streamed, to a locally deployed instance and
receive a correct response that was scheduled through admission control,
queueing, and a GPU-backed worker, with the full request path observable in
metrics and traces, and with reproducible benchmark results checked into the
repository.

## Main components

- API gateway: OpenAI-compatible HTTP surface, request validation, streaming.
- Control plane: model registry, routing policy, worker membership, config.
- Scheduler: admission control, queueing, batching, dispatch to workers.
- Inference adapter: integration layer to a concrete inference backend.
- Metrics collector: aggregation and export of serving metrics.
- Operator console: read-only operational view for debugging the running system.

## Core workflow

1. Client sends a chat completion request to the API gateway.
2. Gateway validates the request and submits it to the scheduler.
3. Scheduler applies admission control: accept, queue, or reject with a reason.
4. Accepted requests are batched and dispatched to an inference worker through
   the adapter.
5. Tokens stream back through the gateway to the client. Cancellation propagates
   end to end.
6. The control plane decides which model and worker pool serve the request.
7. Every stage emits metrics and trace spans to the metrics collector.

## Phase outputs

- Architecture Phase: repository skeleton and architecture documents. (current)
- Serving Phase: working API gateway, scheduler, and adapter for a single model.
- Scale Phase: continuous batching, multi-model routing, admission tuning.
- Operations Phase: observability stack, operator console, runbooks.
- Benchmark Phase: reproducible load tests and recorded results.
- Deployment Phase: container images and Kubernetes manifests for one cluster.

## Intentional non-goals

- No model training or fine-tuning.
- No multi-region or multi-cluster orchestration.
- No billing, accounts, or user management product surface.
- No proprietary model weights shipped in the repository.
- No autoscaling controller in the first complete version.

## Local and demo limitations

- Targets a single machine or a single Kubernetes cluster.
- GPU access depends on available hardware. A CPU or mock backend path exists for
  development where no GPU is present.
- Benchmark numbers reflect the demo hardware they were produced on and are not
  presented as production capacity.

## Measurable completion criteria

- A documented local runbook brings the system up and serves a request.
- Streaming and non-streaming chat completion paths both work and are tested.
- Admission control rejects load past a configured limit with a typed error.
- Queue depth, admission decisions, and per-request latency appear in dashboards.
- A benchmark run is reproducible from a committed command and produces results
  stored in `benchmarks/results`.
- Container images build and the system deploys to a single cluster from
  committed manifests.
