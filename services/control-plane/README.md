# Control Plane

Status: Scaffolded (Session 3). Runtime not implemented.
Implementation: Not Started

## Ownership

Process: `services/control-plane`. Package: `control_plane`.

## Responsibilities

- Model registry (`ModelRecord`)
- Routing policy and worker pool membership
- Runtime configuration (queue limits, priority classes)
- Internal read APIs for gateway and scheduler
- Operator write APIs for configuration

## Inputs

- Operator configuration changes
- Worker registration events from adapter

## Outputs

- Model metadata and routing decisions
- Worker membership snapshots
- Configuration version for cache invalidation

## Non-responsibilities

- Per-request admission or queue state
- Dispatch or token streaming
- Metrics aggregation

## Dependencies

- `gpu-inference-common-schemas`
- `gpu-inference-observability`

## Contracts

- `docs/contracts/service-interfaces.md`
- `packages/common-schemas/schemas/model-record.json`
