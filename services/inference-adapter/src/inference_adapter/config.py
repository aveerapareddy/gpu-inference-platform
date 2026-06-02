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


@lru_cache
def get_settings() -> Settings:
    return Settings()
