# Scheduler

Status: Scaffolded (Session 3). Runtime not implemented.
Implementation: Not Started

## Ownership

Process: `services/scheduler`. Package: `scheduler`.

## Responsibilities

- Admission control (accept / reject)
- Bounded queueing per model and priority class
- Batch formation and dispatch to adapter
- Cancel propagation
- `SchedulerState` aggregate mode
- Scheduling metrics emission

## Inputs

- `SubmitRequest` from gateway
- Cancel signals from gateway
- Worker capacity from control plane / adapter

## Outputs

- Admission responses
- `Batch` dispatch commands to adapter
- `StreamingChunk` relay toward gateway
- Queue and admission metrics

## Non-responsibilities

- Client HTTP or SSE
- Model registry writes
- Inference kernel execution

## Dependencies

- `gpu-inference-common-schemas`
- `gpu-inference-observability`

## Contracts

- `docs/architecture/scheduler-design.md`
- `docs/contracts/state-models.md`
