# Scheduler Design

Status: Architecture Phase
Implementation: Not Started

The scheduler is the core of the platform. It decides what runs, when, and on
which worker. This document defines its responsibilities and the policies it must
support. It is a design target.

## Responsibilities

- Admission control: decide accept, queue, or reject for each incoming request.
- Queueing: hold accepted requests in bounded, model-aware queues.
- Batching: group compatible requests for efficient worker execution.
- Dispatch: assign batches to workers within advertised capacity.
- Cancellation: remove queued or in-flight requests on client cancel or
  disconnect.

## Admission control

Admission protects the system from unbounded load. Inputs to the decision
include current queue depth, available worker capacity, the request's model and
priority class, and configured limits.

Outcomes:
- Accept: enqueue immediately.
- Reject: return a typed error (for example, queue full) with a retry hint.

Admission is explicit and observable. Every decision increments a labeled
counter so rejection rates are visible per reason.

## Queueing

- Queues are bounded. A full queue produces a rejection, not unbounded growth.
- Queues are partitioned by model, and within a model by priority class.
- Ordering within a class is fair (for example, FIFO) unless a documented policy
  overrides it.

## Batching

The first target is request-level batching: combine compatible requests into a
single worker call. Compatibility is defined by model and any backend
constraints exposed by the adapter.

Continuous batching, where sequences join and leave an in-flight batch as they
start and finish, is a later milestone. It depends on backend support exposed
through the adapter and is described here as planned, not implemented.

## Dispatch

- The scheduler dispatches only within a worker's advertised capacity.
- Worker selection considers current load and model placement from the control
  plane.
- Dispatch records which worker served each request for tracing and debugging.

## Fairness and priority

Priority classes let some traffic be served ahead of others without starving
lower classes. The exact policy is configurable. The default avoids indefinite
starvation of any class.

## Observability hooks

The scheduler emits: queue depth per model, admission decisions per reason,
time-in-queue, batch size distribution, and dispatch latency. These feed the
metrics collector and the operator console.

## Explicit non-goals here

- No autoscaling of workers in the first complete version.
- No cross-cluster scheduling.
- No speculative or predictive admission; decisions use observed state only.
