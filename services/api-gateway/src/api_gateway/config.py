"""Gateway configuration."""

from __future__ import annotations

from functools import lru_cache
from uuid import uuid4

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GATEWAY_", env_file=".env", extra="ignore")

    host: str = "0.0.0.0"
    port: int = 8080
    service_name: str = "api-gateway"
    gateway_instance_id: str = Field(default_factory=lambda: str(uuid4()))
    max_body_bytes: int = 4 * 1024 * 1024
    max_prompt_chars: int = 32768
    default_max_tokens: int = 256
    require_api_key: bool = True
    # Comma-separated keys for demo; empty allows any non-empty bearer token.
    api_keys: str = ""
    control_plane_integrated: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
