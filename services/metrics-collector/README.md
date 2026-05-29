# Metrics Collector

Status: Not implemented (Architecture Phase)

Receives and aggregates metrics and traces from the other services and exposes
them for Prometheus and Grafana. Owns observability state; core services do not.

See `docs/architecture/observability-and-reliability.md`. No runtime code exists
yet.
