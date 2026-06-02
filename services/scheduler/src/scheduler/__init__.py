"""Scheduler service package. Session 9 — batching mechanics; no inference."""

from scheduler.application import SchedulerApplication, create_application
from scheduler.batch import (
    Batch,
    BatchContext,
    BatchMember,
    BatchResult,
    BatchService,
    BatchSnapshot,
    BatchState,
    BatchStatistics,
    MemberStatus,
)
from scheduler.config import Settings, get_settings
from scheduler.integrations.control_plane import ControlPlaneQueueReader
from scheduler.models.batch_decision import BatchPlacementDecision, BatchRejectionDecision
from scheduler.models.decision import (
    SchedulingCandidate,
    SchedulingDecision,
    SchedulingFailure,
    SchedulingResult,
)
from scheduler.models.state import SchedulerCycle, SchedulerSnapshot, SchedulerState
from scheduler.queue.reader import QueueReader, QueueSnapshotView

__version__ = "0.1.0"

__all__ = [
    "Batch",
    "BatchContext",
    "BatchMember",
    "BatchPlacementDecision",
    "BatchRejectionDecision",
    "BatchResult",
    "BatchService",
    "BatchSnapshot",
    "BatchState",
    "BatchStatistics",
    "ControlPlaneQueueReader",
    "MemberStatus",
    "QueueReader",
    "QueueSnapshotView",
    "SchedulerApplication",
    "SchedulerCycle",
    "SchedulerSnapshot",
    "SchedulerState",
    "SchedulingCandidate",
    "SchedulingDecision",
    "SchedulingFailure",
    "SchedulingResult",
    "Settings",
    "create_application",
    "get_settings",
]
