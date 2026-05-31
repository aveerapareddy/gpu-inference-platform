# Repository Structure Validation

Status: Architecture Phase (Session 2)
Implementation: Not Started

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

## Implementation rule

When Serving Phase starts, the first change in each service is to import or
generate types from `packages/common-schemas/schemas/`. No hand-written duplicate
structs for fields already in schema files.
