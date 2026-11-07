"""Portable agent-sandbox backend, including K3S development clusters."""

import asyncio
import logging
import shlex
from typing import TYPE_CHECKING, override

from k8s_agent_sandbox.exceptions import SandboxNotFoundError
from pydantic_ai.workspaces import CommandResult

from app.clients.sandbox import SnapshotableSandboxClient
from app.config import settings
from app.constants import RESOURCES_DIR

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from k8s_agent_sandbox import SandboxClient as KubernetesClient
    from k8s_agent_sandbox.sandbox import Sandbox

    from app.clients.blob_storage import BlobStorageClient


class KubernetesAgentSandbox(SnapshotableSandboxClient):
    """Use the upstream SDK and immutable archives without GKE-only PodSnapshots.

    Images contain filesystem changes relative to a pinned warm-pool image,
    including system dependencies, permissions, symlinks and deleted files.
    Archives remain in application blob storage after a pod is terminated.
    """

    def __init__(
        self, client: KubernetesClient, blobs: BlobStorageClient, *, warmpool: str, namespace: str = "default"
    ) -> None:
        """Accept cluster connectivity and snapshot storage explicitly."""
        self.client = client
        self.blobs = blobs
        self.warmpool = warmpool
        self.namespace = namespace
        self.machine: Sandbox | None = None

    @override
    async def start(self, name: str, snapshot_id: str | None = None) -> None:
        self.machine = await asyncio.to_thread(
            self.client.create_sandbox,
            self.warmpool,
            namespace=self.namespace,
            claim_name=name,
            adopt_existing=True,
            shutdown_after_seconds=settings.AGENTS_SANDBOX_TIMEOUT,
        )
        await self.execute("mkdir -p /workspace /opt/gitedge")
        await self.write_file("/opt/gitedge/snapshot.py", (RESOURCES_DIR / "agents" / "snapshot.py").read_bytes())
        baseline = await self.execute("python3 /opt/gitedge/snapshot.py baseline", timeout=300)
        if baseline.exit_code:
            raise RuntimeError(baseline.stderr)
        if snapshot_id:
            marker = "/opt/gitedge/restored/" + snapshot_id.rsplit("/", 1)[-1]
            if (await self.execute(f"test -f {shlex.quote(marker)}")).exit_code:
                image = await self.blobs.get(snapshot_id)
                if image is None:
                    raise FileNotFoundError(snapshot_id)
                await self.write_file("/opt/gitedge/image.tar.gz", image)
                restored = await self.execute(
                    f"python3 /opt/gitedge/snapshot.py restore && mkdir -p /opt/gitedge/restored && touch {shlex.quote(marker)}",
                    timeout=300,
                )
                if restored.exit_code:
                    raise RuntimeError(restored.stderr)

    @override
    async def write_file(self, path: str, data: bytes) -> None:
        if self.machine is None or self.machine.files is None:
            raise RuntimeError("Sandbox has not started")
        parent = shlex.quote(path.rsplit("/", 1)[0])
        result = await self.execute(f"mkdir -p {parent}")
        if result.exit_code:
            raise RuntimeError(result.stderr)
        await asyncio.to_thread(self.machine.files.write, path, data, allow_unsafe_paths=True)

    @override
    async def execute(self, command: str, *, timeout: float = 300) -> CommandResult:
        if self.machine is None or self.machine.commands is None:
            raise RuntimeError("Sandbox has not started")
        result = await asyncio.to_thread(
            self.machine.commands.run, command, timeout=int(timeout), command_timeout=timeout
        )
        return CommandResult(exit_code=result.exit_code, stdout=result.stdout, stderr=result.stderr)

    @override
    async def snapshot(self, snapshot_id: str) -> str:
        key = f"agents/snapshots/{snapshot_id}"
        if await self.blobs.get(key) is None:
            result = await self.execute("python3 /opt/gitedge/snapshot.py capture", timeout=300)
            if result.exit_code:
                raise RuntimeError(result.stderr)
            if self.machine is None or self.machine.files is None:
                raise RuntimeError("Sandbox has not started")
            image = await asyncio.to_thread(
                self.machine.files.read, "/opt/gitedge/image.tar.gz", allow_unsafe_paths=True
            )
            await self.blobs.put(key, image)
        return key

    @override
    async def stop(self) -> None:
        if self.machine is not None:
            await asyncio.to_thread(self.machine.terminate)

    @override
    async def stop_named(self, name: str) -> None:
        try:
            machine = await asyncio.to_thread(self.client.get_sandbox, name, namespace=self.namespace)
            await asyncio.to_thread(machine.terminate)
        except SandboxNotFoundError:
            logger.debug("Sandbox %s is already terminated", name)
