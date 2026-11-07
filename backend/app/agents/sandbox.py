"""Lazy, replay-safe handles for tool-only machines."""

import asyncio
from typing import TYPE_CHECKING, override

from app.clients.sandbox import SnapshotableSandboxClient

if TYPE_CHECKING:
    from collections.abc import Callable

    from pydantic_ai.workspaces import CommandResult


class RunSandbox(SnapshotableSandboxClient):
    """Replays that skip completed tool steps must not resume already stopped VMs."""

    def __init__(self, factory: Callable[[], SnapshotableSandboxClient], name: str, snapshot_id: str | None) -> None:
        """Keep only immutable references until a real side effect needs compute."""
        self.factory = factory
        self.name = name
        self.snapshot_id = snapshot_id
        self.machine: SnapshotableSandboxClient | None = None
        self.lock = asyncio.Lock()

    async def ensure(self) -> SnapshotableSandboxClient:
        """Lazily reattach once even when harness tools run concurrently."""
        async with self.lock:
            if self.machine is None:
                machine = self.factory()
                await machine.start(self.name, self.snapshot_id)
                self.machine = machine
            return self.machine

    @override
    async def start(self, name: str, snapshot_id: str | None = None) -> None:
        """Pin configuration without provisioning compute."""
        self.name, self.snapshot_id = name, snapshot_id

    @override
    async def execute(self, command: str, *, timeout: float = 300) -> CommandResult:
        return await (await self.ensure()).execute(command, timeout=timeout)

    @override
    async def snapshot(self, snapshot_id: str) -> str:
        return await (await self.ensure()).snapshot(snapshot_id)

    @override
    async def stop(self) -> None:
        if self.machine is not None:
            await self.machine.stop()
        else:
            # Attach without resume/create if a previous process reached cleanup.
            await self.factory().stop_named(self.name)
