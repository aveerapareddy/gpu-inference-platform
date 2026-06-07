"""vLLM OpenAI-compatible backend. Owner: inference adapter."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import httpx

from common_schemas.batch import Batch as DispatchBatch
from common_schemas.states import MessageRole

from inference_adapter.backend.failures import (
    BackendInternalFailure,
    BackendTimeout,
    BackendUnavailable,
)
from inference_adapter.backend.models import (
    BackendHealthState,
    BackendMetadata,
    BatchSubmitResult,
    CancelRequestResult,
    HealthCheckResult,
    RequestCompletionResult,
    RequestExecutionStatus,
    RequestStatusResult,
)


@dataclass(frozen=True, slots=True)
class VLLMBackendConfig:
    backend_id: str = "vllm"
    base_url: str = "http://127.0.0.1:8000"
    default_model: str = ""
    supported_models: tuple[str, ...] = ()
    max_batch_size: int = 8
    request_timeout_seconds: float = 120.0
    health_timeout_seconds: float = 5.0
    api_key: str | None = None
    tensor_parallel_size: int | None = None
    gpu_memory_utilization: float | None = None

    @classmethod
    def from_values(
        cls,
        *,
        backend_id: str,
        base_url: str,
        default_model: str,
        supported_models: tuple[str, ...] | None = None,
        max_batch_size: int = 8,
        request_timeout_seconds: float = 120.0,
        health_timeout_seconds: float = 5.0,
        api_key: str | None = None,
        tensor_parallel_size: int | None = None,
        gpu_memory_utilization: float | None = None,
    ) -> VLLMBackendConfig:
        models = supported_models or ((default_model,) if default_model else ())
        return cls(
            backend_id=backend_id,
            base_url=base_url.rstrip("/"),
            default_model=default_model,
            supported_models=models,
            max_batch_size=max_batch_size,
            request_timeout_seconds=request_timeout_seconds,
            health_timeout_seconds=health_timeout_seconds,
            api_key=api_key,
            tensor_parallel_size=tensor_parallel_size,
            gpu_memory_utilization=gpu_memory_utilization,
        )


class VLLMBackend:
    """Executes inference via vLLM OpenAI-compatible HTTP API."""

    def __init__(
        self,
        config: VLLMBackendConfig,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._config = config
        self._client = client
        self._owned_client: httpx.AsyncClient | None = None
        self._request_status: dict[UUID, RequestExecutionStatus] = {}
        self._completions: dict[UUID, RequestCompletionResult] = {}
        self._last_health: HealthCheckResult | None = None
        self._loaded_models: tuple[str, ...] = ()

    @property
    def backend_id(self) -> str:
        return self._config.backend_id

    @property
    def config(self) -> VLLMBackendConfig:
        return self._config

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is not None:
            return self._client
        if self._owned_client is None:
            headers = {}
            if self._config.api_key:
                headers["Authorization"] = f"Bearer {self._config.api_key}"
            self._owned_client = httpx.AsyncClient(
                base_url=self._config.base_url,
                headers=headers,
                timeout=self._config.request_timeout_seconds,
            )
        return self._owned_client

    async def close(self) -> None:
        if self._owned_client is not None:
            await self._owned_client.aclose()
            self._owned_client = None

    async def submit_batch(self, batch: DispatchBatch) -> BatchSubmitResult:
        now = datetime.now(timezone.utc)
        if batch.model not in self._config.supported_models and self._config.supported_models:
            return BatchSubmitResult(
                batch_id=batch.batch_id,
                backend_id=self.backend_id,
                accepted=False,
                reason="unsupported_model",
                submitted_at=now,
            )
        if len(batch.assignments) > self._config.max_batch_size:
            return BatchSubmitResult(
                batch_id=batch.batch_id,
                backend_id=self.backend_id,
                accepted=False,
                reason="batch_too_large",
                submitted_at=now,
            )

        health = await self.health_check()
        if health.state == BackendHealthState.UNAVAILABLE.value:
            raise BackendUnavailable(health.message or "vllm unavailable", backend_id=self.backend_id)
        if health.state == BackendHealthState.DEGRADED.value and batch.model not in self._loaded_models:
            return BatchSubmitResult(
                batch_id=batch.batch_id,
                backend_id=self.backend_id,
                accepted=False,
                reason="model_not_loaded",
                submitted_at=now,
            )

        completions: list[RequestCompletionResult] = []
        for assignment in batch.assignments:
            completion = await self._execute_request(
                request_id=assignment.request_id,
                model=batch.model,
                inference_request=assignment.inference_request,
            )
            completions.append(completion)
            if completion.status == RequestExecutionStatus.COMPLETED:
                self._request_status[assignment.request_id] = RequestExecutionStatus.COMPLETED
                self._completions[assignment.request_id] = completion
            else:
                self._request_status[assignment.request_id] = RequestExecutionStatus.FAILED
                return BatchSubmitResult(
                    batch_id=batch.batch_id,
                    backend_id=self.backend_id,
                    accepted=False,
                    reason="inference_execution_failed",
                    submitted_at=now,
                    completions=tuple(completions),
                )

        return BatchSubmitResult(
            batch_id=batch.batch_id,
            backend_id=self.backend_id,
            accepted=True,
            reason="vllm_completed",
            submitted_at=now,
            completions=tuple(completions),
        )

    async def _execute_request(
        self,
        *,
        request_id: UUID,
        model: str,
        inference_request: Any,
    ) -> RequestCompletionResult:
        client = await self._get_client()
        payload = {
            "model": model or self._config.default_model,
            "messages": [
                {"role": _message_role(message.role), "content": message.content}
                for message in inference_request.messages
            ],
            "max_tokens": inference_request.max_tokens,
            "stream": False,
        }
        if inference_request.temperature is not None:
            payload["temperature"] = inference_request.temperature
        if inference_request.top_p is not None:
            payload["top_p"] = inference_request.top_p

        started = time.monotonic()
        try:
            response = await client.post("/v1/chat/completions", json=payload)
        except httpx.TimeoutException as exc:
            raise BackendTimeout(
                f"vllm request timed out after {self._config.request_timeout_seconds}s",
                backend_id=self.backend_id,
            ) from exc
        except httpx.RequestError as exc:
            raise BackendUnavailable(
                f"vllm request failed: {exc}",
                backend_id=self.backend_id,
            ) from exc

        duration_ms = (time.monotonic() - started) * 1000.0
        if response.status_code >= 500:
            raise BackendInternalFailure(
                f"vllm server error: {response.status_code}",
                backend_id=self.backend_id,
            )
        if response.status_code >= 400:
            return RequestCompletionResult(
                request_id=request_id,
                backend_id=self.backend_id,
                generated_text="",
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                finish_reason="error",
                completed_at=datetime.now(timezone.utc),
                execution_duration_ms=duration_ms,
                status=RequestExecutionStatus.FAILED,
            )

        body = response.json()
        choice = (body.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        usage = body.get("usage") or {}
        prompt_tokens = int(usage.get("prompt_tokens") or 0)
        completion_tokens = int(usage.get("completion_tokens") or 0)
        total_tokens = int(usage.get("total_tokens") or prompt_tokens + completion_tokens)
        return RequestCompletionResult(
            request_id=request_id,
            backend_id=self.backend_id,
            generated_text=str(message.get("content") or ""),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            finish_reason=choice.get("finish_reason"),
            completed_at=datetime.now(timezone.utc),
            execution_duration_ms=duration_ms,
            status=RequestExecutionStatus.COMPLETED,
        )

    async def get_request_status(self, request_id: UUID) -> RequestStatusResult:
        status = self._request_status.get(request_id, RequestExecutionStatus.UNKNOWN)
        return RequestStatusResult(
            request_id=request_id,
            backend_id=self.backend_id,
            status=status,
            reason=None if status != RequestExecutionStatus.UNKNOWN else "not_submitted",
        )

    async def get_request_completion(self, request_id: UUID) -> RequestCompletionResult | None:
        return self._completions.get(request_id)

    async def cancel_request(self, request_id: UUID) -> CancelRequestResult:
        if request_id not in self._request_status:
            return CancelRequestResult(
                request_id=request_id,
                backend_id=self.backend_id,
                cancelled=False,
                reason="request_not_found",
            )
        self._request_status[request_id] = RequestExecutionStatus.CANCELLED
        return CancelRequestResult(
            request_id=request_id,
            backend_id=self.backend_id,
            cancelled=True,
            reason="vllm_cancelled",
        )

    async def health_check(self) -> HealthCheckResult:
        checked_at = datetime.now(timezone.utc)
        client = await self._get_client()
        try:
            health_response = await client.get(
                "/health",
                timeout=self._config.health_timeout_seconds,
            )
        except httpx.RequestError as exc:
            result = HealthCheckResult(
                backend_id=self.backend_id,
                healthy=False,
                state=BackendHealthState.UNAVAILABLE.value,
                message=str(exc),
                checked_at=checked_at,
            )
            self._last_health = result
            return result

        if health_response.status_code >= 500:
            result = HealthCheckResult(
                backend_id=self.backend_id,
                healthy=False,
                state=BackendHealthState.UNAVAILABLE.value,
                message=f"health endpoint returned {health_response.status_code}",
                checked_at=checked_at,
            )
            self._last_health = result
            return result

        loaded_models: tuple[str, ...] = ()
        try:
            models_response = await client.get(
                "/v1/models",
                timeout=self._config.health_timeout_seconds,
            )
            if models_response.status_code == 200:
                data = models_response.json().get("data") or []
                loaded_models = tuple(str(item.get("id")) for item in data if item.get("id"))
        except httpx.RequestError:
            loaded_models = ()

        self._loaded_models = loaded_models
        configured = self._config.supported_models or (
            (self._config.default_model,) if self._config.default_model else ()
        )
        if configured and loaded_models:
            model_ready = any(model in loaded_models for model in configured)
            state = BackendHealthState.HEALTHY.value if model_ready else BackendHealthState.DEGRADED.value
            message = "model loaded" if model_ready else "vllm reachable but configured model not loaded"
            healthy = model_ready
        else:
            state = BackendHealthState.HEALTHY.value
            message = "vllm reachable"
            healthy = True

        result = HealthCheckResult(
            backend_id=self.backend_id,
            healthy=healthy,
            state=state,
            message=message,
            checked_at=checked_at,
        )
        self._last_health = result
        return result

    async def backend_metadata(self) -> BackendMetadata:
        health = self._last_health or await self.health_check()
        extra: dict[str, Any] = {
            "base_url": self._config.base_url,
            "loaded_models": list(self._loaded_models),
            "health_state": health.state,
        }
        if self._config.tensor_parallel_size is not None:
            extra["tensor_parallel_size"] = self._config.tensor_parallel_size
        if self._config.gpu_memory_utilization is not None:
            extra["gpu_memory_utilization"] = self._config.gpu_memory_utilization
        return BackendMetadata(
            backend_id=self.backend_id,
            backend_type="vllm",
            supported_models=self._config.supported_models or self._loaded_models,
            max_batch_size=self._config.max_batch_size,
            extra=extra,
        )


def _message_role(role: MessageRole) -> str:
    return role.value
