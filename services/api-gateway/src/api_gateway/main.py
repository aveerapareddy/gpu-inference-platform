"""Entry point for the API gateway process."""

from __future__ import annotations

import uvicorn

from api_gateway.app import create_app
from api_gateway.config import get_settings


def run() -> None:
    settings = get_settings()
    uvicorn.run(
        "api_gateway.app:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
        log_level="info",
    )


if __name__ == "__main__":
    run()
