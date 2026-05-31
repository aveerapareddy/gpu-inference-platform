# Metrics Collector

Status: Scaffolded (Session 3). Runtime not implemented.
Implementation: Not Started

## Ownership

Process: `services/metrics-collector`. Package: `metrics_collector`.

## Responsibilities

- Scrape or receive metrics from platform services
- Enforce naming via `gpu_inference_observability.metrics`
- Expose aggregated Prometheus text (planned)
- Optional `RequestMetrics` push intake

## Inputs

- `GET /metrics` from each service
- Optional push events

## Outputs

- Prometheus-compatible exposition (planned)
- No feedback into request path

## Non-responsibilities

- Request routing or scheduling
- Log storage
- Alerting product

## Dependencies

- `gpu-inference-common-schemas`
- `gpu-inference-observability`

## Contracts

- `docs/contracts/observability-metrics.md`
