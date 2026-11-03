"""Provider-independent sandbox clients for one isolated, short-lived job each."""

import base64
import json
import zlib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from http import HTTPStatus
from typing import TYPE_CHECKING, override
from urllib.parse import urlsplit

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from app.schemas.runners import LinuxRunner, RunnerImage

from aiodocker import Docker
from aiodocker.exceptions import DockerError
from vercel.sandbox import (
    NetworkPolicy,
    NetworkPolicySubnets,
    SandboxApiError,
    SandboxResources,
    SandboxStatus,
    SnapshotSource,
    create_sandbox,
    get_sandbox,
)
from vercel.sandbox import SandboxError as VercelSandboxError


class SandboxError(RuntimeError):
    """A provider could not create, inspect, or clean up a job sandbox."""


@dataclass(frozen=True)
class SandboxExecution:
    """Provider-observed launcher state, independent of job reports."""

    running: bool
    exit_code: int | None = None


class AbstractSandboxClient(ABC):
    """Implement this contract to add another sandbox provider."""

    def __init__(
        self,
        images: Mapping[LinuxRunner, RunnerImage],
        *,
        controller_url: str = "https://gitedge.invalid",
        egress_hosts: Sequence[str] = (),
    ) -> None:
        """Use only operator-configured, prebuilt runner images."""
        self.images = images
        self.controller_url = controller_url
        self.egress_hosts = tuple(egress_hosts)

    def _image(self, runner: LinuxRunner) -> RunnerImage:
        image = self.images.get(runner)
        if image is None:
            raise SandboxError(f"Runner {runner} has no configured image")
        return image

    @abstractmethod
    async def start(
        self, name: str, files: dict[str, bytes], lifetime: int, *, runner: LinuxRunner = "ubuntu-24.04"
    ) -> None:
        """Idempotently start one isolated job under a stable name."""
        ...

    @abstractmethod
    async def status(self, name: str) -> SandboxExecution:
        """Observe the launcher without reading sandbox files or resuming it."""
        ...

    @abstractmethod
    async def delete(self, name: str) -> None:
        """Idempotently destroy a sandbox, including any running commands."""
        ...


MAX_VERCEL_ENV_BYTES = 4096
CLEANUP_GRACE_SECONDS = 30
PRIVATE_SUBNETS = (
    "0.0.0.0/8",
    "10.0.0.0/8",
    "100.64.0.0/10",
    "127.0.0.0/8",
    "169.254.0.0/16",
    "172.16.0.0/12",
    "192.168.0.0/16",
    "192.0.0.0/24",
    "192.0.2.0/24",
    "198.18.0.0/15",
    "198.51.100.0/24",
    "203.0.113.0/24",
    "224.0.0.0/3",
    "::/0",
)


class DockerSandboxClient(AbstractSandboxClient):
    """Run jobs without privileged mode, host source mounts, or a Docker socket."""

    @override
    async def start(
        self, name: str, files: dict[str, bytes], lifetime: int, *, runner: LinuxRunner = "ubuntu-24.04"
    ) -> None:
        config = {
            "Image": self._image(runner).image,
            "Cmd": [
                "timeout",
                "--signal=TERM",
                "--kill-after=10",
                str(lifetime + CLEANUP_GRACE_SECONDS),
                "/usr/local/bin/gitedge-launch",
            ],
            "User": "10001:10001",
            "Env": [
                f"GITEDGE_JOB={files['input.json'].decode()}",
                "HTTP_PROXY=http://gitedge-egress:3128",
                "HTTPS_PROXY=http://gitedge-egress:3128",
                "http_proxy=http://gitedge-egress:3128",
                "https_proxy=http://gitedge-egress:3128",
                "NO_PROXY=127.0.0.1,localhost",
                "no_proxy=127.0.0.1,localhost",
                "NODE_USE_ENV_PROXY=1",
            ],
            "HostConfig": {
                "Memory": 2 * 1024**3,
                "NanoCpus": 2_000_000_000,
                "PidsLimit": 512,
                "CapDrop": ["ALL"],
                "SecurityOpt": ["no-new-privileges:true"],
                "NetworkMode": f"{name}-network",
            },
            "Labels": {"gitedge.actions": "true"},
        }
        try:
            async with Docker(api_version="v1.45") as client:
                await self._egress(client, name, runner, lifetime)
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

    async def _egress(self, client: Docker, name: str, runner: LinuxRunner, lifetime: int) -> None:
        network_name = f"{name}-network"
        try:
            network = await client.networks.get(network_name)
        except DockerError as exc:
            if exc.status != HTTPStatus.NOT_FOUND:
                raise
            network = await client.networks.create(
                {
                    "Name": network_name,
                    "Internal": True,
                    "Driver": "bridge",
                    "Options": {"com.docker.network.bridge.gateway_mode_ipv4": "isolated"},
                }
            )
        try:
            proxy = await client.containers.create(
                config={
                    "Image": self._image(runner).image,
                    "User": "10001:10001",
                    "Cmd": [
                        "timeout",
                        "--signal=KILL",
                        str(lifetime + CLEANUP_GRACE_SECONDS),
                        "bun",
                        "/usr/local/bin/gitedge-egress.mjs",
                    ],
                    "Env": [
                        f"GITEDGE_CONTROLLER={self.controller_url}",
                        f"GITEDGE_EGRESS_HOSTS={json.dumps(self.egress_hosts)}",
                    ],
                    "HostConfig": {
                        "NetworkMode": "bridge",
                        "Memory": 128 * 1024**2,
                        "PidsLimit": 32,
                        "CapDrop": ["ALL"],
                        "SecurityOpt": ["no-new-privileges:true"],
                        "ReadonlyRootfs": True,
                        "ExtraHosts": ["host.docker.internal:host-gateway"],
                    },
                    "Labels": {"gitedge.actions": "true"},
                },
                name=f"{name}-egress",
            )
        except DockerError as exc:
            if exc.status != HTTPStatus.CONFLICT:
                raise
            proxy = await client.containers.get(f"{name}-egress")
        if (await proxy.show())["State"]["Status"] == "created":
            await network.connect({"Container": proxy.id, "EndpointConfig": {"Aliases": ["gitedge-egress"]}})
            await proxy.start()

    @override
    async def status(self, name: str) -> SandboxExecution:
        try:
            async with Docker(api_version="v1.45") as client:
                container = await client.containers.get(name)
                state = (await container.show())["State"]
                running = state["Status"] in {"running", "created"}
                return SandboxExecution(running, None if running else state.get("ExitCode"))
        except DockerError as exc:
            if exc.status == HTTPStatus.NOT_FOUND:
                return SandboxExecution(False)
            raise SandboxError(f"Docker sandbox status failed: {exc}") from exc

    @override
    async def delete(self, name: str) -> None:
        """Remove the container and its anonymous volumes with aiodocker."""
        try:
            async with Docker(api_version="v1.45") as client:
                for handle in (name, f"{name}-egress"):
                    try:
                        container = await client.containers.get(handle)
                        await container.delete(force=True, v=True)
                    except DockerError as exc:
                        if exc.status != HTTPStatus.NOT_FOUND:
                            raise
                try:
                    network = await client.networks.get(f"{name}-network")
                    await network.delete()
                except DockerError as exc:
                    if exc.status != HTTPStatus.NOT_FOUND:
                        raise
        except DockerError as exc:
            raise SandboxError(f"Docker sandbox cleanup failed: {exc}") from exc


class VercelSandboxClient(AbstractSandboxClient):
    """Launch detached one-shot jobs; provider credentials never enter the VM."""

    def __init__(
        self,
        images: Mapping[LinuxRunner, RunnerImage],
        region: str | None = None,
        *,
        controller_url: str = "https://gitedge.invalid",
        egress_hosts: Sequence[str] = (),
    ) -> None:
        """Use prebuilt VCR images or matching snapshots for each Linux release."""
        super().__init__(images, controller_url=controller_url, egress_hosts=egress_hosts)
        self.region = region

    @override
    async def start(
        self, name: str, files: dict[str, bytes], lifetime: int, *, runner: LinuxRunner = "ubuntu-24.04"
    ) -> None:
        """Boot a prepared image and pass only a small job descriptor."""
        image = self._image(runner)
        controller = urlsplit(self.controller_url)
        if controller.scheme != "https" or not controller.hostname:
            raise SandboxError("Vercel jobs require an HTTPS controller URL")
        descriptor = files["input.json"]
        environment = {
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
                    image=None if image.snapshot_id else image.image,
                    source=SnapshotSource(snapshot_id=image.snapshot_id) if image.snapshot_id else None,
                    region=self.region,
                    persistent=False,
                    network_policy=NetworkPolicy.custom(
                        allow={host: [] for host in (*self.egress_hosts, controller.hostname)},
                        subnets=NetworkPolicySubnets(deny=PRIVATE_SUBNETS),
                    ),
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
                "/usr/local/bin/gitedge-launch", kill_after=lifetime + CLEANUP_GRACE_SECONDS, sudo=False
            )
        except VercelSandboxError as exc:
            raise SandboxError(f"Vercel sandbox start failed: {exc}") from exc

    @override
    async def status(self, name: str) -> SandboxExecution:
        try:
            box = await get_sandbox(name=name)
            if box.status != SandboxStatus.RUNNING:
                return SandboxExecution(False)
            processes = await box.query_processes()
            if len(processes) != 1:
                return SandboxExecution(False)
            code = processes[0].returncode
            return SandboxExecution(code is None, code)
        except SandboxApiError as exc:
            if exc.status_code == HTTPStatus.NOT_FOUND:
                return SandboxExecution(False)
            raise SandboxError(f"Vercel sandbox status failed: {exc}") from exc
        except VercelSandboxError as exc:
            raise SandboxError(f"Vercel sandbox status failed: {exc}") from exc

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
