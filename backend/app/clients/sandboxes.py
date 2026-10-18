"""Provider-independent sandbox clients for one isolated, short-lived job each."""

import asyncio
import io
import json
import tarfile
from abc import ABC, abstractmethod
from contextlib import closing
from dataclasses import dataclass, field
from http import HTTPStatus
from pathlib import Path
from typing import override

import docker
from docker.errors import APIError, DockerException, NotFound
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


MAX_FILE_BYTES = 32 * 1024 * 1024
CLEANUP_GRACE_SECONDS = 30
# Read the marker first: if it exists, subsequent result/state reads are complete.
READ_FILES = ("exit-code", "result.json", "log.jsonl", "state.tar.gz", "cache.tar.gz")


class DockerSandboxClient(AbstractSandboxClient):
    """Run jobs without privileged mode, host source mounts, or a Docker socket."""

    def __init__(self, image: str, *, ca_bundle: str | None = None, environment: dict[str, str] | None = None) -> None:
        """Configure the managed local Docker daemon and optional explicit network trust."""
        self.image = image
        self.ca_bundle = ca_bundle
        self.environment = environment or {}

    @override
    async def start(self, name: str, files: dict[str, bytes], lifetime: int) -> None:
        """Create and start from an already-local image; transfer no repository source."""
        await asyncio.to_thread(self._start, name, files, lifetime)

    def _start(self, name: str, files: dict[str, bytes], lifetime: int) -> None:
        try:
            with closing(docker.from_env(version="1.45")) as client:
                env = dict(self.environment)
                env["GITEDGE_JOB"] = files["input.json"].decode()
                env["GITEDGE_RESTORE_URL"] = json.loads(files["input.json"]).get("restore_url", "")
                env["NO_PROXY"] = env.get("NO_PROXY", "localhost,127.0.0.1") + ",host.docker.internal"
                env["no_proxy"] = env["NO_PROXY"]
                volumes = {}
                if self.ca_bundle:
                    volumes[str(Path(self.ca_bundle).resolve())] = {"bind": "/run/gitedge-ca.pem", "mode": "ro"}
                    env.update(
                        dict.fromkeys(
                            (
                                "NODE_EXTRA_CA_CERTS",
                                "SSL_CERT_FILE",
                                "REQUESTS_CA_BUNDLE",
                                "PIP_CERT",
                                "CURL_CA_BUNDLE",
                                "GIT_SSL_CAINFO",
                            ),
                            "/run/gitedge-ca.pem",
                        )
                    )
                host_config = client.api.create_host_config(
                    binds=volumes,
                    mem_limit="2g",
                    nano_cpus=2_000_000_000,
                    pids_limit=512,
                    cap_drop=["ALL"],
                    security_opt=["no-new-privileges:true"],
                    extra_hosts={"host.docker.internal": "host-gateway"},
                )
                try:
                    container = client.api.create_container(
                        self.image,
                        [
                            "timeout",
                            "--signal=TERM",
                            "--kill-after=10",
                            str(lifetime + CLEANUP_GRACE_SECONDS),
                            "/usr/local/bin/gitedge-launch",
                        ],
                        name=name,
                        environment=env,
                        host_config=host_config,
                        volumes=["/run/gitedge-ca.pem"] if self.ca_bundle else [],
                        labels={"gitedge.actions": "true"},
                    )
                    container_id = container["Id"]
                except APIError as exc:
                    if exc.status_code != HTTPStatus.CONFLICT:
                        raise
                    existing = client.api.inspect_container(name)
                    if existing["State"]["Status"] != "created":
                        return
                    container_id = existing["Id"]
                client.api.start(container_id)
        except DockerException as exc:
            raise SandboxError(f"Docker sandbox start failed: {exc}") from exc

    @override
    async def inspect(self, name: str) -> SandboxSnapshot:
        """Collect bounded files; an exited container stays inspectable until cleanup."""
        return await asyncio.to_thread(self._inspect, name)

    @staticmethod
    def _inspect(name: str) -> SandboxSnapshot:
        try:
            with closing(docker.from_env()) as client:
                container = client.containers.get(name)
                result = SandboxSnapshot(running=container.status in {"running", "created"})
                for path in READ_FILES:
                    try:
                        stream, metadata = container.get_archive(f"/gitedge/{path}")
                    except NotFound:
                        continue
                    if metadata["size"] > MAX_FILE_BYTES:
                        raise SandboxError(f"Sandbox file exceeds {MAX_FILE_BYTES} bytes: {path}")
                    raw = io.BytesIO()
                    for chunk in stream:
                        raw.write(chunk)
                        if raw.tell() > MAX_FILE_BYTES + 16384:
                            raise SandboxError("Sandbox response exceeds the transfer limit")
                    raw.seek(0)
                    with tarfile.open(fileobj=raw) as archive:
                        member = archive.next()
                        if member is not None and member.isfile():
                            handle = archive.extractfile(member)
                            if handle is not None:
                                result.files[path] = handle.read(MAX_FILE_BYTES)
                return result
        except DockerException as exc:
            raise SandboxError(f"Docker sandbox inspection failed: {exc}") from exc

    @override
    async def delete(self, name: str) -> None:
        """Remove a container even after a failed or cancelled job."""
        await asyncio.to_thread(self._delete, name)

    @staticmethod
    def _delete(name: str) -> None:
        try:
            with closing(docker.from_env()) as client:
                try:
                    client.containers.get(name).remove(force=True, v=True)
                except NotFound:
                    return
        except DockerException as exc:
            raise SandboxError(f"Docker sandbox cleanup failed: {exc}") from exc


class VercelSandboxClient(AbstractSandboxClient):
    """Launch detached one-shot jobs; provider credentials never enter the VM."""

    def __init__(self, image: str, snapshot_id: str | None = None) -> None:
        """Use an operator-provisioned image containing the JavaScript executor and toolchains."""
        self.image = image
        self.snapshot_id = snapshot_id

    @override
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
                execution_time_limit=lifetime + CLEANUP_GRACE_SECONDS,
                resources=SandboxResources(vcpus=2),
                env={"GITEDGE_JOB": files["input.json"].decode(), "GITEDGE_RESTORE_URL": config.get("restore_url", "")},
            )
            await box.create_process(
                "/usr/local/bin/gitedge-launch", kill_after=lifetime + CLEANUP_GRACE_SECONDS, sudo=True
            )
        except SandboxApiError as exc:
            if exc.status_code != HTTPStatus.CONFLICT:
                raise SandboxError(f"Vercel sandbox start failed: {exc}") from exc
            box = await get_sandbox(name=name)
            if box.status != SandboxStatus.RUNNING:
                raise SandboxError("Job sandbox already stopped") from exc
            if not await box.query_processes():
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
