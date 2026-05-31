"""Control plane configuration."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CONTROL_PLANE_", extra="ignore")

    service_name: str = "control-plane"
    registry_max_entries: int = 10_000
    remove_terminal_after_seconds: int = 3600


@lru_cache
def get_settings() -> Settings:
    return Settings()
