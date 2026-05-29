# Runtime Model

Status: Architecture Phase
Implementation: Not Started

This document describes how work moves through the system at runtime: process
roles, request lifecycle, and the inference backend boundary. It is a design
target.

## Process roles

- Stateless edge: API gateway. Horizontally scalable. Holds per-connection
  streaming state only for the life of a request.
- Coordinating core: scheduler and control plane. The scheduler holds the live
  queue and dispatch state. The control plane holds slower-changing
  configuration and membership.
- Workers: GPU-backed inference processes reached through the inference adapter.
  Workers are replaceable; losing one must not corrupt platform state.

## Request lifecycle

1. Admission: the request is accepted, queued, or rejected. A rejection carries a
   typed reason and, where applicable, a retry hint.
2. Queueing: accepted requests wait in a bounded queue keyed by model and
   priority class.
3. Batching: the scheduler groups compatible requests for a worker. The batching
   policy is defined in `scheduler-design.md`.
4. Execution: the adapter sends the batch to a worker and receives tokens or a
   completion.
5. Streaming and completion: output flows back to the client through the gateway.
6. Cancellation: a client disconnect or cancel propagates from gateway to
   scheduler to worker, freeing capacity.

## Streaming model

Streaming is the primary path. The gateway holds the client connection and
relays incremental tokens. Internal transport between scheduler, adapter, and
worker must support incremental output and mid-stream cancellation. Non-streaming
responses are produced by collecting a stream to completion.

## Inference backend boundary

The platform does not embed a specific inference engine. The inference adapter
defines a narrow interface: submit a batch, stream tokens, cancel. Concrete
backends (a real GPU engine, or a mock/CPU backend for development) implement
that interface. This keeps the scheduler independent of backend internals.

## Capacity and concurrency

Each worker advertises a capacity bound (for example, maximum concurrent
sequences). The scheduler never dispatches beyond advertised capacity. Capacity
changes when workers join or leave; the control plane is the source of
membership and the scheduler reacts to it.

## Failure handling

- Worker loss: in-flight requests on that worker fail with a typed error; the
  scheduler stops dispatching to it and removes it from rotation.
- Overload: admission control sheds load rather than growing the queue without
  bound.
- Gateway loss: affects only the connections on that gateway instance; the core
  and other gateways continue.
