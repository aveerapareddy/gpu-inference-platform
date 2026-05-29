# Storage Design

Status: Architecture Phase
Implementation: Not Started

This document defines what state the platform keeps, where it lives, and what
survives a restart. It is a design target.

## State categories

- Configuration and registry state: model definitions, routing policy, worker
  pool membership. Slower-changing. Must survive restarts. Owned by the control
  plane.
- Live scheduling state: the queue, in-flight assignments, per-worker load. Fast-
  changing. Treated as disposable; rebuilt from current membership and incoming
  traffic after a restart.
- Observability state: metrics and traces. Owned by the metrics stack
  (Prometheus and the metrics collector), not by core services.
- Request and response payloads: not persisted by default. The platform is a
  serving layer, not a log of conversations.

## Durability rules

- Anything required to bring the control plane back to a known configuration is
  persisted in a defined store under `infra/db`.
- Live scheduling state is in memory. A restart drops queued requests; clients
  retry. This is an accepted tradeoff for simplicity in the target system.
- No component depends on another component's in-memory state surviving a
  restart.

## Store choices

The concrete database for configuration and registry state is selected at the
start of the Serving Phase and documented in `infra/db`. The selection favors a
simple, well-understood store over a feature-rich one. Until then no specific
database is assumed.

## Data ownership

- The control plane is the only writer of configuration and registry state.
- The scheduler owns live scheduling state and exposes it read-only to the
  operator console and metrics collector.
- Schemas for any persisted records live in `packages/common-schemas` so
  producers and consumers agree on shape.

## Retention

- Metrics retention is configured in the Prometheus setup under
  `infra/prometheus`.
- No long-term storage of request payloads in the first complete version.

## Explicit non-goals here

- No distributed consensus store in the first complete version.
- No conversation history or memory feature.
- No analytics warehouse.
