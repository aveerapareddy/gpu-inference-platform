# Inference Adapter

Status: Scaffolded (Session 3). Runtime not implemented.
Implementation: Not Started

## Ownership

Process: `services/inference-adapter`. Package: `inference_adapter`.

## Responsibilities

- Translate `Batch` to backend calls
- Emit `StreamingChunk` and `CompletionResult`
- Report `BackendState` and capacity
- Implement cancel on backend
- Map backend errors to `FailureRecord` vocabulary

## Inputs

- `Batch` from scheduler
- Cancel from scheduler

## Outputs

- Token stream to scheduler
- Worker registration to control plane
- GPU and decode metrics (names from observability package)

## Non-responsibilities

- Admission or queue ordering
- Client HTTP
- Routing policy

## Dependencies

- `gpu-inference-common-schemas`
- `gpu-inference-observability`

## Contracts

- `docs/architecture/runtime-model.md` (backend boundary)
- `docs/contracts/service-interfaces.md`
