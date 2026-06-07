"""Streaming domain models. Owner: gpu_inference_observability.streaming."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4


class StreamLifecycleState(StrEnum):
    STREAM_CREATED = "stream_created"
    STREAM_ACTIVE = "stream_active"
    STREAM_COMPLETED = "stream_completed"
    STREAM_CANCELLED = "stream_cancelled"
    STREAM_FAILED = "stream_failed"


@dataclass(frozen=True, slots=True)
class StreamChunk:
    stream_id: UUID
    request_id: UUID
    index: int
    delta_text: str
    finish_reason: str | None
    timestamp: datetime
    is_first: bool = False


@dataclass
class StreamContext:
    stream_id: UUID
    request_id: UUID
    correlation_id: str
    model: str
    backend_id: str | None
    batch_id: UUID | None
    request_received_time: datetime
    stream: bool = True


@dataclass
class StreamTimingMeasurements:
    request_received_time: datetime
    first_token_time: datetime | None = None
    completion_time: datetime | None = None
    token_timestamps: list[datetime] = field(default_factory=list)

    @property
    def ttft_ms(self) -> float | None:
        if self.first_token_time is None:
            return None
        return (self.first_token_time - self.request_received_time).total_seconds() * 1000.0

    def record_token(self, timestamp: datetime | None = None) -> None:
        ts = timestamp or datetime.now(timezone.utc)
        if self.first_token_time is None:
            self.first_token_time = ts
        self.token_timestamps.append(ts)

    def inter_token_latencies_ms(self) -> tuple[float, ...]:
        if len(self.token_timestamps) < 2:
            return ()
        latencies: list[float] = []
        previous = self.token_timestamps[0]
        for current in self.token_timestamps[1:]:
            latencies.append((current - previous).total_seconds() * 1000.0)
            previous = current
        return tuple(latencies)

    @staticmethod
    def percentile(values: tuple[float, ...], pct: float) -> float | None:
        if not values:
            return None
        ordered = sorted(values)
        index = int(round((pct / 100.0) * (len(ordered) - 1)))
        return ordered[max(0, min(index, len(ordered) - 1))]

    @property
    def itl_ms_p50(self) -> float | None:
        return self.percentile(self.inter_token_latencies_ms(), 50.0)

    @property
    def itl_ms_p99(self) -> float | None:
        return self.percentile(self.inter_token_latencies_ms(), 99.0)


@dataclass
class StreamSession:
    context: StreamContext
    state: StreamLifecycleState = StreamLifecycleState.STREAM_CREATED
    timing: StreamTimingMeasurements = field(default_factory=lambda: StreamTimingMeasurements(
        request_received_time=datetime.now(timezone.utc)
    ))
    generated_text: str = ""
    token_count: int = 0
    error: str | None = None

    @classmethod
    def create(
        cls,
        *,
        request_id: UUID,
        correlation_id: str,
        model: str,
        received_at: datetime | None = None,
    ) -> StreamSession:
        received = received_at or datetime.now(timezone.utc)
        stream_id = uuid4()
        return cls(
            context=StreamContext(
                stream_id=stream_id,
                request_id=request_id,
                correlation_id=correlation_id,
                model=model,
                backend_id=None,
                batch_id=None,
                request_received_time=received,
            ),
            timing=StreamTimingMeasurements(request_received_time=received),
        )

    @property
    def stream_id(self) -> UUID:
        return self.context.stream_id

    @property
    def request_id(self) -> UUID:
        return self.context.request_id


@dataclass(frozen=True, slots=True)
class StreamResult:
    stream_id: UUID
    request_id: UUID
    state: StreamLifecycleState
    generated_text: str
    token_count: int
    ttft_ms: float | None
    itl_ms_samples: tuple[float, ...]
    itl_ms_p50: float | None
    itl_ms_p99: float | None
    completion_time: datetime | None
    finish_reason: str | None = None
    error: str | None = None

    @classmethod
    def from_session(cls, session: StreamSession) -> StreamResult:
        itl = session.timing.inter_token_latencies_ms()
        return cls(
            stream_id=session.stream_id,
            request_id=session.request_id,
            state=session.state,
            generated_text=session.generated_text,
            token_count=session.token_count,
            ttft_ms=session.timing.ttft_ms,
            itl_ms_samples=itl,
            itl_ms_p50=session.timing.itl_ms_p50,
            itl_ms_p99=session.timing.itl_ms_p99,
            completion_time=session.timing.completion_time,
            finish_reason="stop" if session.state == StreamLifecycleState.STREAM_COMPLETED else None,
            error=session.error,
        )
