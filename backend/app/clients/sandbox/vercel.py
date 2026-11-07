"""Vercel sandbox implementation shared by Actions and Agents."""

from typing import override

from pydantic_ai.workspaces import CommandResult
from vercel.sandbox import Sandbox, SnapshotSource, get_or_create_sandbox

from app.clients.sandbox import SnapshotableSandboxClient


class VercelSandboxClient(SnapshotableSandboxClient):
    """Native Vercel filesystem snapshots with named, reattachable machines."""

    def __init__(self) -> None:
        """Use deployment OIDC credentials without forwarding them into the machine."""
        self.machine: Sandbox | None = None

    @override
    async def start(self, name: str, snapshot_id: str | None = None) -> None:
        self.machine, _created = await get_or_create_sandbox(
            name=name,
            source=SnapshotSource(snapshot_id=snapshot_id) if snapshot_id else None,
            persistent=True,
        )
        await self.execute("mkdir -p /workspace /opt/gitedge")

    @override
    async def execute(self, command: str, *, timeout: float = 300) -> CommandResult:
        if self.machine is None:
            raise RuntimeError("Sandbox has not started")
        result = await self.machine.run_process(
            "bash", ["-c", command], capture_output=True, kill_after=timeout, sudo=True
        )
        return CommandResult(exit_code=result.returncode, stdout=result.stdout or "", stderr=result.stderr or "")

    @override
    async def snapshot(self, snapshot_id: str) -> str:
        if self.machine is None:
            raise RuntimeError("Sandbox has not started")
        image = await self.machine.snapshot()
        return image.id

    @override
    async def stop(self) -> None:
        if self.machine is not None:
            await self.machine.stop()
