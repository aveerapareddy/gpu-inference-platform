"""Control plane service."""

from control_plane.application import ControlPlaneApplication, create_application
from control_plane.lifecycle import LifecycleManager

__version__ = "0.1.0"

__all__ = ["ControlPlaneApplication", "LifecycleManager", "create_application", "__version__"]
