# Observability and Reliability

Status: Architecture Phase
Implementation: Not Started

This document defines what the platform must expose to be operable and how it is
expected to behave under failure. It is a design target. No metrics or numbers
here are claimed as measured.

## Signals

- Metrics: counters and histograms for admission decisions, queue depth, time-in-
  queue, batch size, dispatch latency, worker load, and end-to-end request
  latency. Exposed for Prometheus.
- Traces: a span per request stage (gateway, admission, queue, dispatch, worker)
  so a single request can be followed end to end.
- Logs: structured logs with a request identifier that ties log lines to traces.

All services use `packages/observability` so labels and field names are
consistent across the system.

## Key metrics (definitions, not values)

- Admission decisions, labeled by outcome and reason.
- Queue depth per model and priority class.
- Time-in-queue distribution.
- Batch size distribution.
- Dispatch and worker execution latency.
- End-to-end request latency, streaming and non-streaming.
- Active and failed workers.

## Reliability expectations

- Bounded queues: the system rejects past a configured limit instead of growing
  latency without bound.
- Typed failures: every rejection and error carries a machine-readable reason
  that appears in metrics.
- Isolation: a worker failure removes that worker from rotation and fails only
  its in-flight requests.
- Graceful degradation: under sustained overload the system sheds load and keeps
  serving admitted requests within their expected latency.

## Health and readiness

Each service exposes a health endpoint (process is up) and, where meaningful, a
readiness endpoint (able to serve). The scheduler reports readiness based on
having at least one usable worker.

## Operator visibility

The operator console presents live queue depth, worker status, and recent
requests with their outcomes. It is read-only and intended for debugging a
running system, described in `docs/runbooks/local-runbook.md`.

## Explicit non-goals here

- No alerting product; alert rules are example configuration only.
- No SLO commitments during development; targets are documented intent.
