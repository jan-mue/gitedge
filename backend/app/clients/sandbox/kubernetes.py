"""Portable agent-sandbox backend, including K3S development clusters."""

import asyncio
import base64
import shlex
from typing import TYPE_CHECKING, override

from pydantic_ai.workspaces import CommandResult

from app.clients.sandbox import SnapshotableSandboxClient

if TYPE_CHECKING:
    from k8s_agent_sandbox import SandboxClient as KubernetesClient
    from k8s_agent_sandbox.sandbox import Sandbox

    from app.clients.blob_storage import BlobStorageClient


class KubernetesAgentSandbox(SnapshotableSandboxClient):
    """Use the upstream SDK and immutable archives without GKE-only PodSnapshots.

    Portable images contain /workspace and /opt/gitedge. Install dependencies in
    these prefixes; the cluster's warm-pool image supplies system dependencies.
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
        )
        await self.execute("mkdir -p /workspace /opt/gitedge")
        if snapshot_id:
            # A marker prevents a retry from overwriting edits in an adopted pod.
            marker = shlex.quote(f"/opt/gitedge/.restored-{snapshot_id.rsplit('/', 1)[-1]}")
            check = await self.execute(f"test -f {marker}")
            if check.exit_code:
                image = await self.blobs.get(snapshot_id)
                if image is None:
                    raise FileNotFoundError(snapshot_id)
                await self.write_file("/opt/gitedge-restore.tar.gz", image)
                result = await self.execute(f"tar -xzf /opt/gitedge-restore.tar.gz -C / && touch {marker}")
                if result.exit_code:
                    raise RuntimeError(result.stderr)

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
            result = await self.execute("bash -o pipefail -c 'tar -cz -C / workspace opt/gitedge | base64 -w0'")
            if result.exit_code:
                raise RuntimeError(result.stderr)
            await self.blobs.put(key, base64.b64decode(result.stdout, validate=True))
        return key

    @override
    async def stop(self) -> None:
        if self.machine is not None:
            await asyncio.to_thread(self.machine.terminate)
