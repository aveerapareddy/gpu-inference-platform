# Routing and Model Selection

**Status:** Implemented (Session 20)  
**Owner:** control-plane (model registry, routing engine, policies), inference-adapter (backend registry snapshots), scheduler (dispatch integration)

## Scope

This document describes model and backend routing for the embedded platform stack. It does not cover cost optimization, dynamic load balancing, autoscaling, or multi-region routing.

## Architecture

```
Client request (model_id)
  ↓
Gateway validation → ModelRegistry.get_model()
  ↓
Control plane lifecycle → QUEUED
  ↓
Scheduler batch placement (by model string)
  ↓
RoutingEngine.route(request_id, model_id)
  ↓
BatchDispatchService → adapter.submit_batch(backend_id)
  ↓
Execution
```

Routing decisions are made at dispatch time in the scheduler. The gateway validates model availability; the routing engine selects the backend.

## Routing Abstractions

Location: `packages/common-schemas/src/common_schemas/routing.py`

| Type | Role |
|------|------|
| `RoutingCandidate` | Evaluated backend option with tier and health metadata |
| `RoutingDecision` | Selected route: `route_id`, `model_id`, `backend_id`, `policy_name`, fallback flags |
| `RoutingResult` | Success/failure wrapper with candidates and error |
| `RoutableBackendSnapshot` | Adapter-provided backend view (no vLLM/mock implementation details) |

Policy implementations: `services/control-plane/src/control_plane/routing/policies.py`

| Policy | Selection rule |
|--------|----------------|
| `ExplicitModelPolicy` | `ModelRecord.backend` when healthy and supports model |
| `LatencyTierPolicy` | Backend whose `latency_tier` matches `ModelRecord.capabilities.latency_tier` |
| `QualityTierPolicy` | Backend whose `quality_tier` matches `ModelRecord.capabilities.quality_tier` |
| `FallbackPolicy` | Primary policy first; on failure uses `ModelRecord.fallback_backend` |

Policy selection is driven by `ModelRecord.routing_policy`.

## Model Registry

Location: `services/control-plane/src/control_plane/registry/model_registry.py`

| Method | Behavior |
|--------|----------|
| `register_model(record)` | Add or replace model entry |
| `remove_model(model_id)` | Remove entry |
| `list_models()` | All registered models |
| `get_model(model_id)` | Lookup; `None` if unknown |

Each `ModelRecord` stores:

- `model_id`, `backend`, `pool_id`
- token limits
- `capabilities` (`latency_tier`, `quality_tier`, `supports_streaming`)
- `routing_policy`, `fallback_backend`, `metadata`

Default registry registers: `demo`, `example-model`, `demo-fast`, `demo-quality`, `demo-fallback`.

Gateway model lookup uses `control_plane.model_registry` when integrated.

## Backend Registry

Location: `services/inference-adapter/src/inference_adapter/registry/registry.py`

`RegisteredBackend` tracks:

- `state` (HEALTHY, DEGRADED, UNHEALTHY, etc.)
- `supported_models`
- `latency_tier`, `quality_tier`
- `max_batch_size` (capacity hint)
- `metadata`

`list_routable_snapshots()` produces `RoutableBackendSnapshot` tuples for the routing engine. Health is derived from adapter state after health checks.

Embedded stack registers routing backends via `api_gateway/runtime/routing_setup.py`: `mock`, `mock-fast`, `mock-quality`, `mock-primary` (unhealthy, for fallback tests).

## Fallback Behavior

**At routing time (`FallbackPolicy`):**

Primary backend from inner policy is skipped when unhealthy or unsupported. Configured `fallback_backend` is selected. Emits `fallback_invoked` trace event.

**At dispatch time (`BatchDispatchService`):**

If `submit_batch` raises or returns rejected, the failed `backend_id` is excluded and routing is retried. Preserves request trace context; lifecycle fails only when no backend remains.

| Condition | Result |
|-----------|--------|
| Model not in registry | `routing_failed` before dispatch |
| Primary backend unhealthy | Fallback policy selects alternate |
| All backends exhausted | Batch dispatch rejected; request may reach FAILED |
| Backend degraded | Treated as routable (`healthy=True` for DEGRADED) |

## Observability

**Trace/log events** (`RoutingEventEmitter`):

- `routing_started`
- `model_selected`
- `backend_selected`
- `routing_completed`
- `fallback_invoked`
- `routing_failed`

Each event includes `request_id`, `route_id` (when assigned), `model_id`, `backend_id`, timestamp.

**Prometheus metrics:**

- `gpu_inference_routing_decisions_total{model_id, backend_id}`
- `gpu_inference_routing_failures_total{model_id}`
- `gpu_inference_fallback_invocations_total{model_id}`
- `gpu_inference_model_requests_total{model_id}`
- `gpu_inference_backend_selection_total{backend_id}`

## Validation

`runtime-validation/routing_validation.py` covers:

- Explicit model routing (`demo` → `mock`)
- Latency tier routing (`demo-fast` → `mock-fast`)
- Quality tier routing (`demo-quality` → `mock-quality`)
- Backend failure fallback (`demo-fallback` → `mock` via fallback)
- Unavailable model routing failure

Run: `python runtime-validation/routing_validation.py`

## Limitations

- Routing is in-process only; no distributed routing table or staleness TTL.
- One backend per batch dispatch; no split routing within a batch.
- Policy selection is per-model, not per-request override from client headers.
- `supported_models` empty on a backend means all models allowed (compatibility default).
- No load-based or cost-based optimization.
- Scheduler still groups batches by model string only; pool_id is not used for queue partitioning yet.

## Planned / Not Implemented

- Cost optimization policies
- Dynamic load balancing across backends
- Autoscaling-driven routing
- Multi-region routing
- HTTP model registry API (registry is in-memory)
