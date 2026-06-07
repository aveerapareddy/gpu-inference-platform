"""Convert backend completion to shared schema."""

from __future__ import annotations

from common_schemas.completion import InferenceCompletionRecord

from inference_adapter.backend.models import RequestCompletionResult


def to_completion_record(result: RequestCompletionResult) -> InferenceCompletionRecord:
    return InferenceCompletionRecord(
        request_id=result.request_id,
        backend_id=result.backend_id,
        generated_text=result.generated_text,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        total_tokens=result.total_tokens,
        finish_reason=result.finish_reason,
        completed_at=result.completed_at,
        execution_duration_ms=result.execution_duration_ms,
    )
