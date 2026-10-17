"""Vercel microVM adapter using the installed asynchronous Python Sandbox SDK."""

import json
from http import HTTPStatus

from vercel.sandbox import (
    SandboxApiError,
    SandboxPathNotFoundError,
    SandboxResources,
    SandboxStatus,
    SnapshotSource,
    create_sandbox,
    get_sandbox,
)
from vercel.sandbox import (
    SandboxError as VercelSandboxError,
)

from app.clients.sandboxes.base import MAX_FILE_BYTES, READ_FILES, SandboxError, SandboxSnapshot


class VercelSandboxClient:
    """Launch detached one-shot jobs; provider credentials never enter the VM."""

    def __init__(self, image: str, snapshot_id: str | None = None) -> None:
        """Use an operator-provisioned image containing gitedge-exec and toolchains."""
        self.image = image
        self.snapshot_id = snapshot_id

    async def start(self, name: str, files: dict[str, bytes], lifetime: int) -> None:
        """Boot a prepared snapshot and pass only a small job descriptor."""
        if not self.snapshot_id:
            raise SandboxError("Vercel jobs require ACTIONS_VERCEL_SNAPSHOT prepared before dispatch")
        config = json.loads(files["input.json"])
        try:
            box = await create_sandbox(
                name=name,
                image=None,
                source=SnapshotSource(snapshot_id=self.snapshot_id),
                persistent=False,
                execution_time_limit=lifetime,
                resources=SandboxResources(vcpus=2),
                env={"GITEDGE_JOB": files["input.json"].decode(), "GITEDGE_RESTORE_URL": config.get("restore_url", "")},
            )
            await box.create_process("/usr/local/bin/gitedge-launch", kill_after=lifetime, sudo=True)
        except SandboxApiError as exc:
            if exc.status_code != HTTPStatus.CONFLICT:
                raise SandboxError(f"Vercel sandbox start failed: {exc}") from exc
            box = await get_sandbox(name=name)
            if box.status != SandboxStatus.RUNNING:
                raise SandboxError("Job sandbox already stopped") from exc
            if not await box.query_processes():
                await box.create_process("/usr/local/bin/gitedge-launch", kill_after=lifetime, sudo=True)
        except VercelSandboxError as exc:
            raise SandboxError(f"Vercel sandbox start failed: {exc}") from exc

    async def inspect(self, name: str) -> SandboxSnapshot:
        """Read an active job without auto-resuming an expired session."""
        try:
            box = await get_sandbox(name=name)
            if box.status != SandboxStatus.RUNNING:
                return SandboxSnapshot(running=False)
            result = SandboxSnapshot(running=False)
            for process in await box.query_processes():
                await process.refresh()
                result.running |= process.returncode is None
            for path in READ_FILES:
                try:
                    data = await box.fs.read_bytes(f"/gitedge/{path}")
                except SandboxPathNotFoundError:
                    continue
                if len(data) > MAX_FILE_BYTES:
                    raise SandboxError(f"Sandbox file too large: {path}")
                result.files[path] = data
            return result
        except VercelSandboxError as exc:
            raise SandboxError(f"Vercel sandbox inspection failed: {exc}") from exc

    async def delete(self, name: str) -> None:
        """Destroy all job resources instead of leaving a persistent snapshot."""
        try:
            box = await get_sandbox(name=name)
            await box.destroy()
        except SandboxApiError as exc:
            if exc.status_code != HTTPStatus.NOT_FOUND:
                raise SandboxError(f"Vercel sandbox cleanup failed: {exc}") from exc
        except VercelSandboxError as exc:
            raise SandboxError(f"Vercel sandbox cleanup failed: {exc}") from exc
