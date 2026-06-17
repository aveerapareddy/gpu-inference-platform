"""FIFO candidate selection. Delegates to FIFOSchedulerPolicy."""

from __future__ import annotations

from scheduler.policies.fifo import FIFOSchedulerPolicy

FifoSelector = FIFOSchedulerPolicy

__all__ = ["FifoSelector", "FIFOSchedulerPolicy"]
