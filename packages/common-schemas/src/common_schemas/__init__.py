"""GPU Inference Platform shared schemas."""

from common_schemas.batch import Batch, BatchAssignment
from common_schemas.failures import FailureRecord
from common_schemas.inference_request import (
    InferenceRequest,
    Message,
    ModelRecord,
    RequestContext,
    SubmitRequest,
)
from common_schemas.inference_response import (
    CompletionResult,
    InferenceResponse,
    StreamingChunk,
    TokenUsage,
)
from common_schemas.metrics import RequestMetrics
from common_schemas.queue import QueueItem
from common_schemas.states import (
    BATCH_FAILURE_STATES,
    BATCH_TERMINAL_STATES,
    BACKEND_FAILURE_STATES,
    BACKEND_TERMINAL_STATES,
    REQUEST_FAILURE_STATES,
    REQUEST_TERMINAL_STATES,
    SCHEDULER_FAILURE_STATES,
    SCHEDULER_TERMINAL_STATES,
    BackendState,
    BatchState,
    Component,
    FailureReason,
    FinishReason,
    MessageRole,
    PriorityClass,
    RequestState,
    SchedulerState,
    TerminalStatus,
    is_failure_request_state,
    is_terminal_request_state,
)

__all__ = [
    "BATCH_FAILURE_STATES",
    "BATCH_TERMINAL_STATES",
    "BACKEND_FAILURE_STATES",
    "BACKEND_TERMINAL_STATES",
    "REQUEST_FAILURE_STATES",
    "REQUEST_TERMINAL_STATES",
    "SCHEDULER_FAILURE_STATES",
    "SCHEDULER_TERMINAL_STATES",
    "BackendState",
    "Batch",
    "BatchAssignment",
    "BatchState",
    "CompletionResult",
    "Component",
    "FailureReason",
    "FailureRecord",
    "FinishReason",
    "InferenceRequest",
    "InferenceResponse",
    "Message",
    "MessageRole",
    "ModelRecord",
    "PriorityClass",
    "QueueItem",
    "RequestContext",
    "RequestMetrics",
    "RequestState",
    "SchedulerState",
    "StreamingChunk",
    "SubmitRequest",
    "TerminalStatus",
    "TokenUsage",
    "is_failure_request_state",
    "is_terminal_request_state",
]

__version__ = "0.1.0"
