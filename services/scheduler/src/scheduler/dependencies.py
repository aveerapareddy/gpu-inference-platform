"""Dependency wiring for SchedulerApplication."""

from __future__ import annotations

from functools import lru_cache

from scheduler.application import SchedulerApplication, create_application
from scheduler.config import Settings, get_settings
from scheduler.queue.reader import QueueReader


def create_application_with_reader(
    queue_reader: QueueReader,
    settings: Settings | None = None,
) -> SchedulerApplication:
    return create_application(queue_reader, settings=settings)


@lru_cache
def get_application_for_reader(reader_id: int) -> SchedulerApplication:
    raise RuntimeError("use create_application_with_reader(queue_reader) for embedded wiring")
