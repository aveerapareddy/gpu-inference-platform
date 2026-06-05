# Database (`infra/db`)

**Status:** Session 17 implements runtime observability persistence in SQLite via `gpu_inference_observability.persistence`.

**Not implemented:** PostgreSQL migrations, control-plane config persistence, production deployment scripts.

## Current scope

Runtime persistence (Session 17):

- Execution records
- Request metadata and lifecycle transitions
- Scheduler and batch decisions
- Failure records
- Replay executions and comparisons
- Trace summaries

Module: `packages/observability/src/gpu_inference_observability/persistence/sqlite/`

Enable via `create_platform_stack(db_path="...")`.

## Planned scope

Control-plane configuration and registry state persistence per `docs/architecture/storage-design.md`. Not started.

## Documentation

[docs/architecture/runtime-persistence.md](../docs/architecture/runtime-persistence.md)
