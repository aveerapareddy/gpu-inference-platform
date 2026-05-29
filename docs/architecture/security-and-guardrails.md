# Security and Guardrails

Status: Architecture Phase
Implementation: Not Started

This document defines the security boundaries and request guardrails for the
platform. It is a design target. It describes the demonstration scope, not a
hardened production posture.

## Trust boundaries

- Client to gateway: untrusted input. All requests are validated against schemas
  before any further processing.
- Gateway to core: trusted internal network in the demo deployment. Services
  authenticate to each other where the deployment makes that practical.
- Core to worker: trusted internal network. Workers accept work only from the
  scheduler.

## Authentication and authorization

- The API gateway supports API-key authentication on the client surface,
  consistent with the OpenAI-compatible convention (bearer token).
- Authorization in the first complete version is coarse: a valid key may submit
  requests. Fine-grained per-model or per-tenant authorization is a documented
  later option, not an initial goal.

## Input guardrails

- Schema validation rejects malformed requests before admission.
- Request limits (maximum tokens, maximum prompt size, allowed models) are
  enforced at the gateway and are configurable.
- Oversized or disallowed requests are rejected with a typed error, the same
  rejection path used by admission control.

## Resource guardrails

- Admission control and bounded queues are the primary protection against
  resource exhaustion.
- Per-key rate limiting is a planned guardrail at the gateway. It is documented
  here as planned, not implemented.

## Secrets

- API keys and backend credentials are supplied through configuration and
  environment, never committed to the repository.
- No model weights or credentials are stored in version control.

## Explicit non-goals here

- No end-user identity, accounts, or login product.
- No content moderation or safety classification of model output.
- No compliance certification claims.
