# API Gateway

Status: Scaffolded (Session 3). Runtime not implemented.
Implementation: Not Started

## Ownership

Process: `services/api-gateway`. Package: `api_gateway`.

## Responsibilities

- Terminate client HTTP (`POST /v1/chat/completions`, `POST /v1/completions`)
- Authenticate API keys
- Validate bodies against shared schemas
- Resolve models via control plane
- Submit work to scheduler; relay streaming responses
- Propagate client cancel to scheduler
- Expose `/health`, `/ready`, `/metrics`

## Inputs

- Client HTTP requests
- Control plane model registry responses
- Scheduler submit and stream responses

## Outputs

- HTTP responses (JSON or SSE)
- Internal `SubmitRequest` to scheduler
- Per-request logs, traces, and metrics

## Non-responsibilities

- Admission control, queueing, batching, dispatch
- Worker or adapter calls
- Model registry writes
- Request payload persistence

## Dependencies

- `gpu-inference-common-schemas`
- `gpu-inference-observability`

## Contracts

- `api-specs/openapi.yaml`
- `docs/contracts/openai-api.md`
- `docs/contracts/service-interfaces.md`
