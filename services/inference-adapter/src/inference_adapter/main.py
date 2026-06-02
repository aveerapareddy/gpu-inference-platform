"""Inference adapter process entry (no HTTP server in Session 10)."""

from __future__ import annotations

import asyncio

from inference_adapter.application import create_application


async def _run() -> None:
    app = create_application()
    await app.startup()
    try:
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        pass
    finally:
        await app.shutdown()


def run() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    run()
