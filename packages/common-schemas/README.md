# common-schemas

Status: Implemented (Session 3 — typed models)
Implementation: Package installable; no service runtime

Python package `common_schemas` (distribution: `gpu-inference-common-schemas`).

## Install

```bash
pip install -e packages/common-schemas
```

## Modules

| Module | Types |
| --- | --- |
| `states.py` | RequestState, BatchState, BackendState, SchedulerState, enums, terminal/failure sets |
| `inference_request.py` | InferenceRequest, RequestContext, SubmitRequest, ModelRecord, Message |
| `inference_response.py` | InferenceResponse, StreamingChunk, CompletionResult, TokenUsage |
| `queue.py` | QueueItem |
| `batch.py` | Batch, BatchAssignment |
| `metrics.py` | RequestMetrics |
| `failures.py` | FailureRecord |

JSON Schema files in `schemas/` remain the contract reference for non-Python
consumers. Pydantic models must stay aligned with those files.

## Usage

```python
from common_schemas import InferenceRequest, RequestState, is_terminal_request_state
```

Documentation: `docs/contracts/runtime-schemas.md`, `docs/contracts/state-models.md`.
