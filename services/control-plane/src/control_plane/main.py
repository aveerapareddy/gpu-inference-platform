"""Control plane process entry (no HTTP server in Session 5)."""

from __future__ import annotations

import asyncio

from control_plane.dependencies import get_application


async def _run() -> None:
    app = get_application()
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
