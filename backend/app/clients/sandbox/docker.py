"""Local Actions execution without snapshot capabilities."""

import asyncio
import logging
from typing import TYPE_CHECKING, override

import docker
from docker.errors import NotFound
from pydantic_ai.workspaces import CommandResult

from app.clients.sandbox import SandboxClient

if TYPE_CHECKING:
    from docker.models.containers import Container

logger = logging.getLogger(__name__)


class DockerSandboxClient(SandboxClient):
    """Ephemeral local runner; deliberately not a SnapshotableSandboxClient."""

    def __init__(self, image: str = "ubuntu:24.04") -> None:
        """Use the local Docker daemon without forwarding application credentials."""
        self.client = docker.from_env()
        self.image = image
        self.machine: Container | None = None

    async def start(self, name: str) -> None:
        """Start an isolated ephemeral container for an Actions job."""
        self.machine = await asyncio.to_thread(
            self.client.containers.run,
            self.image,
            ["sleep", "infinity"],
            name=name,
            detach=True,
            mem_limit="2g",
            pids_limit=256,
        )

    @override
    async def execute(self, command: str, *, timeout: float = 300) -> CommandResult:
        if self.machine is None:
            raise RuntimeError("Sandbox has not started")
        result = await asyncio.to_thread(
            self.machine.exec_run, ["timeout", "--kill-after=5s", str(timeout), "bash", "-c", command], demux=True
        )
        stdout, stderr = result.output
        return CommandResult(
            exit_code=result.exit_code,
            stdout=(stdout or b"").decode(errors="replace"),
            stderr=(stderr or b"").decode(errors="replace"),
        )

    @override
    async def stop(self) -> None:
        if self.machine is not None:
            try:
                await asyncio.to_thread(self.machine.remove, force=True)
            except NotFound:
                logger.debug("Docker sandbox is already removed")
