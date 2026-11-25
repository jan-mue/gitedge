"""Vercel Sandbox as a PydanticAI capability and workspace backend."""

import asyncio
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.workspaces import CommandResult, SupportsCommands, WorkspaceBackend, WorkspaceRef
from vercel.sandbox import SnapshotSource

from app.config import settings
from app.sandboxes import shell_command, validate_timeout

if TYPE_CHECKING:
    from collections.abc import Mapping

    from pydantic_ai import RunContext
    from pydantic_ai.workspaces import WorkspaceCommand
    from vercel.sandbox import Sandbox, SandboxClient


class VercelSandboxBackend(WorkspaceBackend, SupportsCommands):
    """Use an injected standalone SDK client for native sandbox operations."""

    def __init__(
        self,
        client: SandboxClient,
        *,
        name: str | None = None,
        ref: WorkspaceRef | None = None,
        snapshot_id: str | None = None,
    ) -> None:
        """Defer creation/attachment until the first workspace operation."""
        if ref is not None and ref.provider != "vercel":
            raise ValueError("Expected a Vercel workspace ref")
        self.client = client
        self.name = ref.id if ref is not None else name or f"gitedge-{uuid.uuid4()}"
        self._ref = ref
        self.snapshot_id = snapshot_id
        self.machine: Sandbox | None = None
        self.lock = asyncio.Lock()

    @property
    @override
    def ref(self) -> WorkspaceRef | None:
        return self._ref

    async def get_sandbox(self) -> Sandbox:
        """Create or attach once using the injected SDK client."""
        async with self.lock:
            if self.machine is None:
                if self._ref is not None:
                    self.machine = await self.client.get_sandbox(name=self._ref.id)
                else:
                    self.machine, _created = await self.client.get_or_create_sandbox(
                        name=self.name,
                        source=SnapshotSource(snapshot_id=self.snapshot_id) if self.snapshot_id else None,
                        persistent=True,
                        execution_time_limit=settings.AGENTS_SANDBOX_TIMEOUT,
                    )
                    self._ref = WorkspaceRef(provider="vercel", id=self.name)
                result = await self.machine.run_process(
                    "mkdir", ["-p", "/workspace", "/opt/gitedge"], capture_output=True, sudo=True
                )
                if result.returncode:
                    raise RuntimeError(result.stderr)
            return self.machine

    @override
    async def working_dir(self) -> str:
        await self.get_sandbox()
        return "/workspace"

    @override
    async def run(
        self,
        command: WorkspaceCommand,
        *,
        shell: bool = False,
        env: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> CommandResult:
        validate_timeout(timeout)
        script = shell_command(command, shell=shell, env=env)
        machine = await self.get_sandbox()
        result = await machine.run_process(
            "/bin/sh", ["-c", script], capture_output=True, kill_after=timeout, sudo=True
        )
        return CommandResult(exit_code=result.returncode, stdout=result.stdout or "", stderr=result.stderr or "")

    async def snapshot(self) -> str:
        """Use Vercel's native filesystem snapshots."""
        return (await (await self.get_sandbox()).snapshot()).id

    async def stop(self) -> None:
        """Fetch without resuming when cleanup is replayed on a fresh backend."""
        machine = self.machine or await self.client.get_sandbox(name=self.name)
        await machine.stop()
        self.machine = None


@dataclass(kw_only=True)
class VercelSandbox[AgentDepsT](AbstractCapability[AgentDepsT]):
    """Supply the injected Vercel client as a standard workspace capability."""

    client: SandboxClient

    @override
    def get_workspace(self, ctx: RunContext[AgentDepsT], *, ref: WorkspaceRef | None) -> WorkspaceBackend | None:
        if ref is not None and ref.provider != "vercel":
            return None
        return VercelSandboxBackend(self.client, ref=ref)
