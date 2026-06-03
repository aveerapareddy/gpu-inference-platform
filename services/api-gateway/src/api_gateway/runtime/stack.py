"""Embedded platform stack: control plane, scheduler, inference adapter."""

from __future__ import annotations

from dataclasses import dataclass

from control_plane.application import ControlPlaneApplication, create_application as create_cp
from inference_adapter.application import InferenceAdapterApplication, create_application as create_adapter
from scheduler import ControlPlaneQueueReader, create_application as create_scheduler
from scheduler.integrations.embedded_adapter import EmbeddedAdapterClient


@dataclass
class PlatformStack:
    control_plane: ControlPlaneApplication
    scheduler: object
    adapter: InferenceAdapterApplication

    async def startup(self) -> None:
        await self.control_plane.startup()
        await self.adapter.startup()
        await self.scheduler.startup()

    async def shutdown(self) -> None:
        await self.scheduler.shutdown()
        await self.adapter.shutdown()
        await self.control_plane.shutdown()


def create_platform_stack() -> PlatformStack:
    cp = create_cp()
    adapter = create_adapter()
    scheduler = create_scheduler(
        ControlPlaneQueueReader(cp.queue),
        adapter_client=EmbeddedAdapterClient(adapter),
    )
    return PlatformStack(control_plane=cp, scheduler=scheduler, adapter=adapter)
