"""Scheduler process entry (no HTTP server in Session 8)."""

from __future__ import annotations

import asyncio
import sys

from scheduler.config import get_settings


async def _run() -> None:
    settings = get_settings()
    print(
        "scheduler requires a queue reader; embed with control plane or pass QueueReader",
        file=sys.stderr,
    )
    print(
        f"configured tick_interval_ms={settings.tick_interval_ms} "
        f"max_candidate_requests={settings.max_candidate_requests}",
        file=sys.stderr,
    )
    await asyncio.Event().wait()


def run() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    run()
