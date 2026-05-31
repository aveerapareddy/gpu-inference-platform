# Core Runtime Schemas

Status: Architecture Phase (Session 2 — contracts locked)
Implementation: Not Started

JSON Schema files: `packages/common-schemas/schemas/`.

Types are strongly typed in schema (types, enums, required fields). Implementations
generate language bindings; they do not add undeclared fields on the wire.

## Type index

| Schema file | Owner | Lifecycle |
| --- | --- | --- |
| `inference-request.json` | API gateway (creates), scheduler (reads) | VALIDATED -> terminal |
| `inference-response.json` | Scheduler/adapter (creates), gateway (reads) | SCHEDULED -> COMPLETED |
| `request-context.json` | API gateway (creates), all services (read) | RECEIVED -> terminal |
| `queue-item.json` | Scheduler | ADMITTED -> SCHEDULED or terminal |
| `batch.json` | Scheduler | Created at dispatch -> terminal |
| `batch-assignment.json` | Scheduler | Part of batch |
| `streaming-chunk.json` | Adapter (creates), gateway (reads) | DECODING -> STREAMING |
| `completion-result.json` | Adapter/scheduler | Terminal success |
| `request-metrics.json` | All services (append), metrics collector (aggregates) | RECEIVED -> terminal |
| `failure-record.json` | Component that detects failure | Terminal |

## InferenceRequest

Internal representation after gateway validation. Submitted to scheduler.

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `request_id` | string (uuid) | yes | Generated at gateway |
| `model` | string | yes | Registry id |
| `messages` | Message[] | yes | Normalized chat messages |
| `stream` | boolean | yes | |
| `max_tokens` | integer | yes | Resolved default applied |
| `temperature` | number | no | |
| `top_p` | number | no | |
| `priority_class` | enum | no | Default `default`; set by policy |
| `api_key_id` | string | no | Hash or id for rate limit; not raw key |
| `client_request_id` | string | no | Optional client `X-Request-Id` |

Ownership: gateway constructs; scheduler mutates only `priority_class` if
reclassified at admission.

## InferenceResponse

Wrapper for non-streaming completion or metadata on stream end.

| Field | Type | Required |
| --- | --- | --- |
| `request_id` | string | yes |
| `model` | string | yes |
| `choices` | Choice[] | yes |
| `usage` | TokenUsage | no |
| `finish_reason` | enum | yes |

## RequestContext

Propagated in logs, traces, and internal RPC headers.

| Field | Type | Required |
| --- | --- | --- |
| `request_id` | string | yes |
| `trace_id` | string | yes |
| `span_id` | string | yes |
| `arrival_time` | string (RFC3339) | yes |
| `model` | string | yes |
| `stream` | boolean | yes |
| `gateway_instance_id` | string | yes |

Ownership: gateway creates; downstream services copy, do not mutate `request_id`
or `arrival_time`.

## QueueItem

Scheduler queue entry.

| Field | Type | Required |
| --- | --- | --- |
| `request_id` | string | yes |
| `inference_request` | InferenceRequest | yes |
| `request_context` | RequestContext | yes |
| `enqueued_at` | string (RFC3339) | yes |
| `priority_class` | enum | yes |
| `queue_name` | string | yes | `{model}/{priority_class}` |

Lifecycle: created at ADMITTED/QUEUED; deleted on SCHEDULED or terminal.

## Batch

Dispatch unit sent to adapter.

| Field | Type | Required |
| --- | --- | --- |
| `batch_id` | string (uuid) | yes |
| `model` | string | yes |
| `worker_id` | string | yes |
| `assignments` | BatchAssignment[] | yes |
| `created_at` | string (RFC3339) | yes |
| `max_batch_tokens` | integer | no | Backend limit |

Lifecycle: scheduler creates at dispatch; adapter reports terminal batch state.

## BatchAssignment

| Field | Type | Required |
| --- | --- | --- |
| `request_id` | string | yes |
| `slot_index` | integer | yes | 0-based in batch |
| `inference_request` | InferenceRequest | yes |

## StreamingChunk

| Field | Type | Required |
| --- | --- | --- |
| `request_id` | string | yes |
| `batch_id` | string | yes |
| `index` | integer | yes | Monotonic per request |
| `delta_text` | string | yes | May be empty |
| `finish_reason` | enum or null | yes |
| `created_at` | string (RFC3339) | yes |

Emitted by adapter; scheduler relays; gateway maps to SSE.

## CompletionResult

| Field | Type | Required |
| --- | --- | --- |
| `request_id` | string | yes |
| `status` | enum | yes | `completed` |
| `finish_reason` | enum | yes |
| `usage` | TokenUsage | no |
| `completed_at` | string (RFC3339) | yes |

## RequestMetrics

Terminal or periodic snapshot for observability contract.

| Field | Type | Required |
| --- | --- | --- |
| `request_id` | string | yes |
| `model` | string | yes |
| `backend` | string | no |
| `status` | enum | yes |
| `failure_reason` | enum or null | yes |
| `arrival_time` | string | yes |
| `queue_wait_ms` | integer | no |
| `scheduling_ms` | integer | no |
| `ttft_ms` | integer | no |
| `itl_ms_p50` | number | no | Computed from samples |
| `itl_ms_p99` | number | no |
| `completion_ms` | integer | no |
| `token_count` | integer | no |
| `worker_id` | string | no |
| `batch_id` | string | no |

Ownership: each service writes its segment; metrics collector merges for export.

## FailureRecord

| Field | Type | Required |
| --- | --- | --- |
| `request_id` | string | yes |
| `status` | enum | yes | `failed`, `rejected`, `timed_out`, `cancelled` |
| `failure_reason` | enum | yes |
| `failed_at` | string (RFC3339) | yes |
| `component` | enum | yes | `gateway`, `control_plane`, `scheduler`, `adapter`, `worker` |
| `message` | string | no |
| `last_state` | enum | no | Platform RequestState at failure |

## Shared enums

Defined in `enums.json` and referenced by other schemas:

- `RequestState`, `BatchState`, `BackendState`, `SchedulerState`
- `FailureReason`, `FinishReason`, `PriorityClass`, `TerminalStatus`

See `state-models.md` for transition rules.
