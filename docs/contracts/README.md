# Contracts

Status: Architecture Phase (Session 2 contracts; Session 3 Python models)
Implementation: Typed models in packages/common-schemas; HTTP not served

This directory is the human-readable contract index. Machine-readable definitions
live in `api-specs/` (HTTP) and `packages/common-schemas/schemas/` (runtime).

| Document | Deliverable |
| --- | --- |
| [openai-api.md](openai-api.md) | Client-facing HTTP API |
| [runtime-schemas.md](runtime-schemas.md) | Core runtime types |
| [state-models.md](state-models.md) | Request, batch, backend, scheduler states |
| [service-interfaces.md](service-interfaces.md) | Inter-service contracts |
| [observability-metrics.md](observability-metrics.md) | Metric names and schemas |
| [repository-structure.md](repository-structure.md) | Layout validation (Session 2) |

Session 1 behavior (workflow, boundaries) is unchanged. Contracts formalize
types and interfaces implementation must conform to.
