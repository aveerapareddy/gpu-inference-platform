"""Inference adapter configuration."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="INFERENCE_ADAPTER_",
        env_file=".env",
        extra="ignore",
    )

    service_name: str = "inference-adapter"
    default_backend_id: str = "mock"
    register_mock_backend: bool = True
    register_vllm_backend: bool = False

    vllm_base_url: str = Field(default="http://127.0.0.1:8000")
    vllm_model: str = Field(default="")
    vllm_supported_models: str = Field(default="")
    vllm_max_batch_size: int = Field(default=8, ge=1)
    vllm_request_timeout_seconds: float = Field(default=120.0, gt=0)
    vllm_health_timeout_seconds: float = Field(default=5.0, gt=0)
    vllm_api_key: str | None = None
    vllm_tensor_parallel_size: int | None = Field(default=None, ge=1)
    vllm_gpu_memory_utilization: float | None = Field(default=None, gt=0.0, le=1.0)

    def parsed_vllm_supported_models(self) -> tuple[str, ...]:
        if not self.vllm_supported_models.strip():
            if self.vllm_model.strip():
                return (self.vllm_model.strip(),)
            return ()
        return tuple(item.strip() for item in self.vllm_supported_models.split(",") if item.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
