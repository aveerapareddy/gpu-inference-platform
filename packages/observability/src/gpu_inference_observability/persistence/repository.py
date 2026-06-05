"""Repository abstractions. Owner: gpu_inference_observability.persistence."""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from gpu_inference_observability.runtime.models import FailureRecord, RuntimeComponent, TraceTimeline
from gpu_inference_observability.runtime.replay.models import ExecutionComparison, ReplayResult, RequestExecutionRecord
from gpu_inference_observability.persistence.models import (
    BatchDecision,
    LifecycleTransition,
    PersistedFailureRecord,
    ReplayComparisonRecord,
    ReplayExecution,
    RequestMetadata,
    SchedulerDecision,
    TraceSummary,
)


class ExecutionRecordRepository(ABC):
    @abstractmethod
    def save(self, record: RequestExecutionRecord) -> None: ...

    @abstractmethod
    def get(self, request_id: UUID) -> RequestExecutionRecord | None: ...

    @abstractmethod
    def list_request_ids(self) -> list[UUID]: ...

    @abstractmethod
    def delete(self, request_id: UUID) -> bool: ...


class LifecycleRepository(ABC):
    @abstractmethod
    def save_transitions(self, request_id: UUID, transitions: tuple[LifecycleTransition, ...]) -> None: ...

    @abstractmethod
    def get_transitions(self, request_id: UUID) -> tuple[LifecycleTransition, ...]: ...


class ReplayRepository(ABC):
    @abstractmethod
    def save_replay(self, replay: ReplayExecution) -> None: ...

    @abstractmethod
    def get_replay(self, replay_id: UUID) -> ReplayExecution | None: ...

    @abstractmethod
    def list_replays(self, *, source_request_id: UUID | None = None) -> list[ReplayExecution]: ...

    @abstractmethod
    def save_comparison(self, comparison: ReplayComparisonRecord) -> None: ...

    @abstractmethod
    def get_comparison(self, comparison_id: UUID) -> ReplayComparisonRecord | None: ...


class FailureRepository(ABC):
    @abstractmethod
    def save_failures(self, failures: tuple[PersistedFailureRecord, ...]) -> None: ...

    @abstractmethod
    def query_failures(self, *, limit: int = 100) -> list[PersistedFailureRecord]: ...

    @abstractmethod
    def query_failures_by_request(self, request_id: UUID) -> list[PersistedFailureRecord]: ...

    @abstractmethod
    def query_failures_by_component(self, component: RuntimeComponent) -> list[PersistedFailureRecord]: ...


class TraceRepository(ABC):
    @abstractmethod
    def save_summary(self, summary: TraceSummary) -> None: ...

    @abstractmethod
    def get_summary(self, request_id: UUID) -> TraceSummary | None: ...


class RequestRepository(ABC):
    @abstractmethod
    def save_request(self, metadata: RequestMetadata) -> None: ...

    @abstractmethod
    def get_request(self, request_id: UUID) -> RequestMetadata | None: ...

    @abstractmethod
    def list_requests(self) -> list[RequestMetadata]: ...

    @abstractmethod
    def delete_request(self, request_id: UUID) -> bool: ...


class SchedulerDecisionRepository(ABC):
    @abstractmethod
    def save_decisions(self, decisions: tuple[SchedulerDecision, ...]) -> None: ...

    @abstractmethod
    def get_decisions(self, request_id: UUID) -> tuple[SchedulerDecision, ...]: ...


class BatchDecisionRepository(ABC):
    @abstractmethod
    def save_decisions(self, decisions: tuple[BatchDecision, ...]) -> None: ...

    @abstractmethod
    def get_decisions(self, request_id: UUID) -> tuple[BatchDecision, ...]: ...


class RuntimeRepository(ABC):
    """Facade over durable runtime persistence. Runtime depends on this interface only."""

    @property
    @abstractmethod
    def execution_records(self) -> ExecutionRecordRepository: ...

    @property
    @abstractmethod
    def requests(self) -> RequestRepository: ...

    @property
    @abstractmethod
    def lifecycle(self) -> LifecycleRepository: ...

    @property
    @abstractmethod
    def replays(self) -> ReplayRepository: ...

    @property
    @abstractmethod
    def failures(self) -> FailureRepository: ...

    @property
    @abstractmethod
    def traces(self) -> TraceRepository: ...

    @property
    @abstractmethod
    def scheduler_decisions(self) -> SchedulerDecisionRepository: ...

    @property
    @abstractmethod
    def batch_decisions(self) -> BatchDecisionRepository: ...

    @abstractmethod
    def persist_execution_record(
        self,
        record: RequestExecutionRecord,
        *,
        timeline: TraceTimeline | None = None,
    ) -> None: ...

    @abstractmethod
    def persist_replay_result(
        self,
        result: ReplayResult,
        *,
        started_at,
        completed_at,
        comparison: ExecutionComparison | None = None,
    ) -> None: ...

    @abstractmethod
    def close(self) -> None: ...

    @abstractmethod
    def commit(self) -> None: ...
