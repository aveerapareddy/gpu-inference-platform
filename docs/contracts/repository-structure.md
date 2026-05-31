# Repository Structure Validation

Status: Architecture Phase (Session 3 review)
Implementation: Shared packages and service scaffolds exist; no service runtime

## Verdict

The Session 0 layout is sufficient for implementation. Two additions are required
before Serving Phase code:

| Addition | Rationale |
| --- | --- |
| `api-specs/` | OpenAPI is the standard contract artifact for HTTP APIs (Envoy, Kubernetes API patterns). Keeps client surface separate from internal schemas. |
| `packages/common-schemas/schemas/` | JSON Schema files are the versioned source of truth for cross-service messages. Implementations generate bindings; they do not redefine fields. |

No new services, workflows, or infrastructure components are introduced.

## Not added (and why)

| Path | Decision |
| --- | --- |
| `shared/contracts/` | Redundant with `packages/common-schemas`. One schema home avoids drift. |
| `proto/` | gRPC is not in v1 architecture. HTTP + JSON internal RPC matches gateway surface. Add only if a future session mandates gRPC. |
| Per-service `contracts/` subdirs | Central package enforces single ownership of types. Services import schemas, not copy them. |

## Existing paths (validated)

| Path | Role |
| --- | --- |
| `services/*` | Runtime binaries; one README per service until code lands |
| `packages/common-schemas` | Schema definitions (JSON Schema in Session 2) |
| `packages/observability` | Metric naming conventions + contract doc |
| `docs/contracts` | Contract prose and cross-references |
| `docs/architecture` | Session 1 design authority; contracts must not contradict |
| `infra/*` | Deferred until Serving/Operations phases |

## Package layout after Session 2

```
api-specs/
  openapi.yaml          # Client HTTP (planned; not served)
  README.md

packages/common-schemas/
  schemas/              # JSON Schema draft-07
  README.md

packages/observability/
  contracts/
    metrics.md          # Pointer to docs/contracts/observability-metrics.md
  README.md

docs/contracts/         # This directory
```

## Session 3 additions

| Path | Status |
| --- | --- |
| `packages/common-schemas/src/common_schemas/` | Pydantic v2 models (source of truth for Python) |
| `packages/observability/src/gpu_inference_observability/` | Logging, tracing, metric name scaffolding |
| `services/*/pyproject.toml` + `src/*/__init__.py` | Per-service skeleton (5 services) |
| `pyproject.toml` (root) | uv workspace pointers for local dev |

## Session 3 review findings

| Item | Action |
| --- | --- |
| `shared/contracts/` | Still not needed |
| `operator-console/` | README only; UI deferred. Add `pyproject.toml` when UI session starts |
| `api-specs/internal-openapi.yaml` | Future Work; internal paths documented in prose only |
| JSON Schema vs Pydantic drift | CI check (Future Work): validate models against `schemas/` |

No additional packages required before gateway implementation.

## Implementation rule

Services import `common_schemas` types. Do not duplicate field definitions.
JSON Schema files remain for contract review and non-Python tooling.
