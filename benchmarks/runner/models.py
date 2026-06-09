"""Benchmark result models. Owner: benchmarks.runner."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class HardwareMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    platform: str
    python_version: str
    cpu_model: str | None = None
    ram_bytes: int | None = None
    gpu_model: str | None = None
    gpu_memory_total_bytes: int | None = None
    gpu_count: int = 0
    gpu_source: str = "unknown"
    hostname: str | None = None


class ModelMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_id: str
    backend_id: str | None = None
    max_output_tokens: int | None = None
    stream: bool = False
    configuration: dict[str, Any] = Field(default_factory=dict)


class BenchmarkScenario(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    name: str
    description: str = ""
    concurrency: int = Field(ge=1)
    request_count: int = Field(ge=1)
    workload_profile: str
    stream: bool = False
    mixed_stream_ratio: float | None = Field(default=None, ge=0.0, le=1.0)


class BenchmarkResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_index: int
    request_id: str | None = None
    success: bool
    error: str | None = None
    latency_ms: float | None = Field(default=None, ge=0.0)
    ttft_ms: float | None = Field(default=None, ge=0.0)
    itl_ms_samples: tuple[float, ...] = Field(default_factory=tuple)
    queue_wait_ms: float | None = Field(default=None, ge=0.0)
    scheduler_latency_ms: float | None = Field(default=None, ge=0.0)
    batch_latency_ms: float | None = Field(default=None, ge=0.0)
    stream: bool = False
    prompt_chars: int = 0
    max_tokens: int = 0


class BenchmarkSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_requests: int
    successful_requests: int
    failed_requests: int
    throughput_rps: float | None = None
    latency_ms_p50: float | None = None
    latency_ms_p99: float | None = None
    ttft_ms_p50: float | None = None
    ttft_ms_p99: float | None = None
    itl_ms_p50: float | None = None
    queue_wait_ms_p50: float | None = None
    duration_seconds: float


class BenchmarkRun(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: UUID = Field(default_factory=uuid4)
    scenario: BenchmarkScenario
    hardware: HardwareMetadata
    model: ModelMetadata
    started_at: datetime
    completed_at: datetime | None = None
    results: tuple[BenchmarkResult, ...] = Field(default_factory=tuple)
    summary: BenchmarkSummary | None = None
    metrics_snapshot: dict[str, float] = Field(default_factory=dict)
    runner: str = "embedded"
