"""Provider-independent sandbox clients for one isolated, short-lived job each."""

import asyncio
import base64
import io
import json
import tarfile
import zlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from http import HTTPStatus
from typing import override

from aiodocker import Docker
from aiodocker.exceptions import DockerError
from vercel.sandbox import (
    SandboxApiError,
    SandboxPathNotFoundError,
    SandboxResources,
    SandboxStatus,
    SnapshotSource,
    create_sandbox,
    get_sandbox,
)
from vercel.sandbox import SandboxError as VercelSandboxError


class SandboxError(RuntimeError):
    """A provider could not create, inspect, or clean up a job sandbox."""


@dataclass
class SandboxSnapshot:
    """Bounded data read from a job sandbox."""

    running: bool
    files: dict[str, bytes] = field(default_factory=dict)


class AbstractSandboxClient(ABC):
    """Implement this contract to add another sandbox provider."""

    @abstractmethod
    async def start(self, name: str, files: dict[str, bytes], lifetime: int) -> None:
        """Idempotently start one isolated job under a stable name."""
        ...

    @abstractmethod
    async def inspect(self, name: str) -> SandboxSnapshot:
        """Read logs/result and portable state without resuming stopped sandboxes."""
        ...

    @abstractmethod
    async def delete(self, name: str) -> None:
        """Idempotently destroy a sandbox, including any running commands."""
        ...


MAX_VERCEL_ENV_BYTES = 4096
MAX_FILE_BYTES = 32 * 1024 * 1024
CLEANUP_GRACE_SECONDS = 30
# Read the marker first: if it exists, subsequent result/state reads are complete.
READ_FILES = ("exit-code", "result.json", "log.jsonl", "state.tar.gz")


class DockerSandboxClient(AbstractSandboxClient):
    """Run jobs without privileged mode, host source mounts, or a Docker socket."""

    def __init__(self, image: str) -> None:
        """Use a locally prepared image."""
        self.image = image

    @override
    async def start(self, name: str, files: dict[str, bytes], lifetime: int) -> None:
        config = {
            "Image": self.image,
            "Cmd": [
                "timeout",
                "--signal=TERM",
                "--kill-after=10",
                str(lifetime + CLEANUP_GRACE_SECONDS),
                "/usr/local/bin/gitedge-launch",
            ],
            "Env": [f"GITEDGE_JOB={files['input.json'].decode()}"],
            "HostConfig": {
                "Memory": 2 * 1024**3,
                "NanoCpus": 2_000_000_000,
                "PidsLimit": 512,
                "CapDrop": ["ALL"],
                "SecurityOpt": ["no-new-privileges:true"],
                "ExtraHosts": ["host.docker.internal:host-gateway"],
            },
            "Labels": {"gitedge.actions": "true"},
        }
        try:
            async with Docker(api_version="v1.45") as client:
                try:
                    container = await client.containers.create(config=config, name=name)
                except DockerError as exc:
                    if exc.status != HTTPStatus.CONFLICT:
                        raise
                    container = await client.containers.get(name)
                    if (await container.show())["State"]["Status"] != "created":
                        return
                await container.start()
        except DockerError as exc:
            raise SandboxError(f"Docker sandbox start failed: {exc}") from exc

    @override
    async def inspect(self, name: str) -> SandboxSnapshot:
        """Stream bounded job files instead of buffering an unbounded SDK archive."""
        try:
            async with Docker(api_version="v1.45") as client:
                container = await client.containers.get(name)
                state = await container.show()
                result = SandboxSnapshot(running=state["State"]["Status"] in {"running", "created"})
                for path in READ_FILES:
                    try:
                        # get_archive buffers its complete response; use aiodocker's
                        # streaming transport so workflow-created files remain bounded.
                        async with client._query(  # noqa: SLF001 — public get_archive buffers the entire response
                            f"containers/{container.id}/archive", method="GET", params={"path": f"/gitedge/{path}"}
                        ) as response:
                            raw = io.BytesIO()
                            async for chunk in response.content.iter_chunked(65536):
                                raw.write(chunk)
                                if raw.tell() > MAX_FILE_BYTES + 16384:
                                    raise SandboxError("Sandbox response exceeds the transfer limit")
                        raw.seek(0)
                        with tarfile.open(fileobj=raw) as archive:
                            member = archive.next()
                            if member is not None and member.isfile():
                                if member.size > MAX_FILE_BYTES:
                                    raise SandboxError(f"Sandbox file exceeds the transfer limit: {path}")
                                handle = archive.extractfile(member)
                                if handle is not None:
                                    result.files[path] = handle.read(MAX_FILE_BYTES)
                    except DockerError as exc:
                        if exc.status != HTTPStatus.NOT_FOUND:
                            raise
                return result
        except DockerError as exc:
            raise SandboxError(f"Docker sandbox inspection failed: {exc}") from exc

    @override
    async def delete(self, name: str) -> None:
        """Remove the container and its anonymous volumes with aiodocker."""
        try:
            async with Docker(api_version="v1.45") as client:
                try:
                    container = await client.containers.get(name)
                    await container.delete(force=True, v=True)
                except DockerError as exc:
                    if exc.status != HTTPStatus.NOT_FOUND:
                        raise
        except DockerError as exc:
            raise SandboxError(f"Docker sandbox cleanup failed: {exc}") from exc


class VercelSandboxClient(AbstractSandboxClient):
    """Launch detached one-shot jobs; provider credentials never enter the VM."""

    def __init__(self, image: str, snapshot_id: str | None = None, region: str | None = None) -> None:
        """Use an operator-provisioned image containing the JavaScript executor and toolchains."""
        self.image = image
        self.snapshot_id = snapshot_id
        self.region = region

    @override
    async def start(self, name: str, files: dict[str, bytes], lifetime: int) -> None:
        """Boot a prepared snapshot and pass only a small job descriptor."""
        if not self.snapshot_id:
            raise SandboxError("Vercel jobs require ACTIONS_VERCEL_SNAPSHOT prepared before dispatch")
        descriptor = files["input.json"]
        environment = {
            "NODE_OPTIONS": "--import=/opt/gitedge/artifact-compat.mjs",
            "RUNNER_TOOL_CACHE": "/opt/hostedtoolcache",
            "AGENT_TOOLSDIRECTORY": "/opt/hostedtoolcache",
        }
        compressed = {
            **environment,
            "GITEDGE_JOB": base64.b64encode(zlib.compress(descriptor)).decode(),
            "GITEDGE_JOB_ENCODING": "deflate",
        }
        # Vercel limits the complete environment payload to 4 KiB. Large workflows
        # use one descriptor-file upload, never a source archive or job-time install.
        inline = len(json.dumps(compressed).encode()) <= MAX_VERCEL_ENV_BYTES
        if inline:
            environment = compressed
        try:
            try:
                box = await create_sandbox(
                    name=name,
                    image=None,
                    source=SnapshotSource(snapshot_id=self.snapshot_id),
                    region=self.region,
                    persistent=False,
                    execution_time_limit=lifetime + CLEANUP_GRACE_SECONDS,
                    resources=SandboxResources(vcpus=2),
                    env=environment,
                )
            except SandboxApiError as exc:
                if exc.status_code != HTTPStatus.CONFLICT:
                    raise
                box = await get_sandbox(name=name)
                if box.status != SandboxStatus.RUNNING:
                    raise SandboxError("Job sandbox already stopped") from exc
                if await box.query_processes():
                    return
            if not inline:
                await box.fs.write_bytes("/gitedge/job.json", descriptor)
            await box.create_process(
                "/usr/local/bin/gitedge-launch", kill_after=lifetime + CLEANUP_GRACE_SECONDS, sudo=True
            )
        except VercelSandboxError as exc:
            raise SandboxError(f"Vercel sandbox start failed: {exc}") from exc

    @override
    async def inspect(self, name: str) -> SandboxSnapshot:
        """Read an active job without auto-resuming an expired session."""
        try:
            box = await get_sandbox(name=name)
            if box.status != SandboxStatus.RUNNING:
                return SandboxSnapshot(running=False)

            async def read(path: str) -> bytes | None:
                try:
                    data = await box.fs.read_bytes(f"/gitedge/{path}")
                except SandboxPathNotFoundError:
                    return None
                if len(data) > MAX_FILE_BYTES:
                    raise SandboxError(f"Sandbox file too large: {path}")
                return data

            marker = await read("exit-code")
            if marker is None:
                processes = await box.query_processes()
                if any(process.returncode is None for process in processes):
                    log = await read("log.jsonl")
                    return SandboxSnapshot(running=True, files={"log.jsonl": log} if log is not None else {})
                # A process can finish after the first marker read. Its result is
                # complete once the marker is observed, without per-process refresh calls.
                marker = await read("exit-code")
            values = await asyncio.gather(*(read(path) for path in READ_FILES[1:]))
            files = {path: data for path, data in zip(READ_FILES[1:], values, strict=True) if data is not None}
            if marker is not None:
                files["exit-code"] = marker
            return SandboxSnapshot(running=False, files=files)
        except VercelSandboxError as exc:
            raise SandboxError(f"Vercel sandbox inspection failed: {exc}") from exc

    @override
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
