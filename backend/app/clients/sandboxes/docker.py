"""Docker Python SDK implementation for local execution and integration tests."""

import asyncio
import io
import json
import tarfile
from contextlib import closing
from http import HTTPStatus
from pathlib import Path

import docker
from docker.errors import APIError, DockerException, NotFound

from app.clients.sandboxes.base import MAX_FILE_BYTES, READ_FILES, SandboxError, SandboxSnapshot


class DockerSandboxClient:
    """Run jobs without privileged mode, host source mounts, or a Docker socket."""

    def __init__(self, image: str, *, ca_bundle: str | None = None, environment: dict[str, str] | None = None) -> None:
        """Configure the managed local Docker daemon and optional explicit network trust."""
        self.image = image
        self.ca_bundle = ca_bundle
        self.environment = environment or {}

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
                        ["timeout", "--signal=TERM", "--kill-after=10", str(lifetime), "/usr/local/bin/gitedge-launch"],
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
