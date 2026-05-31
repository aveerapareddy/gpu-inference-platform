"""Dependency wiring for ControlPlaneApplication."""

from __future__ import annotations

from functools import lru_cache

from control_plane.application import ControlPlaneApplication, create_application
from control_plane.config import Settings, get_settings


@lru_cache
def get_application() -> ControlPlaneApplication:
    return create_application(get_settings())
