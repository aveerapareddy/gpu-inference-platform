# Scheduler

Status: Not implemented (Architecture Phase)

The core of the platform. Performs admission control, bounded queueing, batching,
and dispatch to workers. The only component authorized to assign work to a
worker. Propagates cancellation and emits the platform's primary serving metrics.

See `docs/architecture/scheduler-design.md`. No runtime code exists yet.
