"""Scheduler configuration."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SCHEDULER_",
        env_file=".env",
        extra="ignore",
    )

    service_name: str = "scheduler"
    max_candidate_requests: int = Field(default=10, ge=1)
    tick_interval_ms: int = Field(default=1000, ge=100)
    queue_scan_limit: int = Field(default=100, ge=1)


@lru_cache
def get_settings() -> Settings:
    return Settings()
