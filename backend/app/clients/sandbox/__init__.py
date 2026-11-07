"""Shared sandbox contracts for Actions and Agents."""

import base64
import shlex
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pydantic_ai.workspaces import CommandResult

OutputSink = Callable[[str, str, str, int], Awaitable[None]]


class SandboxClient(ABC):
    """An isolated machine used only for tool execution."""

    @abstractmethod
    async def execute(
        self,
        command: str,
        *,
        timeout: float = 300,  # noqa: ASYNC109 - remote command protocol
    ) -> CommandResult:
        """Run a shell command and return its real exit status."""

    async def write_file(self, path: str, data: bytes) -> None:
        """Transfer bounded chunks without placing secrets in provider credentials."""
        target = shlex.quote(path)
        result = await self.execute(f"mkdir -p $(dirname {target}); : > {target}.b64")
        if result.exit_code:
            raise RuntimeError(result.stderr)
        encoded = base64.b64encode(data).decode()
        for offset in range(0, len(encoded), 32768):
            result = await self.execute(f"printf %s {shlex.quote(encoded[offset : offset + 32768])} >> {target}.b64")
            if result.exit_code:
                raise RuntimeError(result.stderr)
        result = await self.execute(f"base64 -d {target}.b64 > {target} && rm {target}.b64")
        if result.exit_code:
            raise RuntimeError(result.stderr)

    @abstractmethod
    async def stop(self) -> None:
        """Release compute resources."""


class SnapshotableSandboxClient(SandboxClient):
    """A sandbox whose filesystem can be forked between agent turns."""

    @abstractmethod
    async def start(self, name: str, snapshot_id: str | None = None) -> None:
        """Create or attach to a named machine, optionally from a snapshot."""

    async def stop_named(self, name: str) -> None:
        """Stop an existing machine after process loss, without creating a replacement."""
        raise NotImplementedError("Provider does not support named cleanup")

    @abstractmethod
    async def snapshot(self, snapshot_id: str) -> str:
        """Save an immutable filesystem image and return its provider reference."""
