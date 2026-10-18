from __future__ import annotations

import base64
import io
import json
import secrets
import tarfile
import zlib
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import pytest
from aiodocker.exceptions import DockerError
from vercel.sandbox import SandboxStatus

from app.clients.sandboxes import DockerSandboxClient, SandboxError, VercelSandboxClient

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from pytest_mock import MockerFixture


async def test_docker_provisioning_does_not_pull_images_or_upload_source(mocker: MockerFixture) -> None:
    sdk = mocker.MagicMock()
    sdk.__aenter__.return_value = sdk
    container = mocker.Mock()
    container.start = mocker.AsyncMock()
    sdk.containers.create = mocker.AsyncMock(return_value=container)
    mocker.patch("app.clients.sandboxes.Docker", return_value=sdk)
    await DockerSandboxClient("prepared@sha256:abc").start("job", {"input.json": b'{"job":"test"}'}, 60)
    sdk.images.pull.assert_not_called()
    container.start.assert_awaited_once()
    config = sdk.containers.create.call_args.kwargs["config"]
    assert config["Image"] == "prepared@sha256:abc"
    assert config["HostConfig"]["CapDrop"] == ["ALL"]
    assert not config["HostConfig"]["Binds"]
    assert not config["Volumes"]
    assert not any(value.startswith("source=") for value in config["Env"])
    sdk.__aexit__.assert_awaited_once()


async def test_vercel_uses_prepared_snapshot_and_never_receives_source(mocker: MockerFixture) -> None:
    box = mocker.MagicMock()
    box.create_process = mocker.AsyncMock()
    create = mocker.patch("app.clients.sandboxes.create_sandbox", new=mocker.AsyncMock(return_value=box))
    provider = VercelSandboxClient("prepared", "snapshot-123", region="iad1")
    await provider.start("job", {"input.json": b'{"job":"test"}'}, 60)
    kwargs = create.call_args.kwargs
    assert kwargs["region"] == "iad1"
    assert kwargs["persistent"] is False
    assert kwargs["image"] is None
    assert kwargs["source"].snapshot_id == "snapshot-123"
    assert kwargs["env"]["GITEDGE_JOB_ENCODING"] == "deflate"
    assert zlib.decompress(base64.b64decode(kwargs["env"]["GITEDGE_JOB"])) == b'{"job":"test"}'
    assert len(json.dumps(kwargs["env"]).encode()) <= 4096
    box.fs.write_bytes.assert_not_called()


async def test_inspecting_expired_vercel_sandbox_never_resumes_it(mocker: MockerFixture) -> None:
    box = mocker.MagicMock(status=SandboxStatus.STOPPED)
    mocker.patch("app.clients.sandboxes.get_sandbox", new=mocker.AsyncMock(return_value=box))
    result = await VercelSandboxClient("prepared").inspect("job")
    assert result.running is False
    box.query_processes.assert_not_called()
    box.fs.read_bytes.assert_not_called()


async def test_docker_reads_complete_result_when_job_finishes_during_inspection(mocker: MockerFixture) -> None:
    sdk = mocker.MagicMock()
    sdk.__aenter__.return_value = sdk
    container = mocker.Mock(id="job")
    container.show = mocker.AsyncMock(return_value={"State": {"Status": "running"}})
    sdk.containers.get = mocker.AsyncMock(return_value=container)
    expected = {"log.jsonl": b"hello\n", "result.json": b'{"status":"success"}', "exit-code": b"0"}
    finished = False

    @asynccontextmanager
    async def archive(_path: str, *, method: str, params: dict[str, str]) -> AsyncGenerator[object]:
        nonlocal finished
        assert method == "GET"
        name = params["path"].rsplit("/", 1)[-1]
        if name == "exit-code":
            finished = True
        if name not in expected or (name == "result.json" and not finished):
            raise DockerError(404, "No such file")
        output = io.BytesIO()
        with tarfile.open(fileobj=output, mode="w") as tar:
            entry = tarfile.TarInfo(name)
            entry.size = len(expected[name])
            tar.addfile(entry, io.BytesIO(expected[name]))

        async def chunks() -> AsyncGenerator[bytes]:
            yield output.getvalue()

        response = mocker.Mock()
        response.content.iter_chunked.return_value = chunks()
        yield response

    mocker.patch.object(sdk, "_query", side_effect=archive)
    mocker.patch("app.clients.sandboxes.Docker", return_value=sdk)
    snapshot = await DockerSandboxClient("prepared").inspect("job")
    assert snapshot.running
    assert snapshot.files == expected


async def test_vercel_refuses_job_time_image_preparation(mocker: MockerFixture) -> None:
    create = mocker.patch("app.clients.sandboxes.create_sandbox", new=mocker.AsyncMock())
    with pytest.raises(SandboxError, match="prepared before dispatch"):
        await VercelSandboxClient("unprepared-image").start("job", {"input.json": b"{}"}, 60)
    create.assert_not_called()


async def test_vercel_uploads_only_the_descriptor_when_it_exceeds_the_environment_limit(mocker: MockerFixture) -> None:
    box = mocker.MagicMock()
    box.create_process = mocker.AsyncMock()
    box.fs.write_bytes = mocker.AsyncMock()
    create = mocker.patch("app.clients.sandboxes.create_sandbox", new=mocker.AsyncMock(return_value=box))
    descriptor = json.dumps({"job": "test", "value": secrets.token_hex(8192)}).encode()
    await VercelSandboxClient("prepared", "snapshot-123").start("job", {"input.json": descriptor}, 60)
    assert "GITEDGE_JOB" not in create.call_args.kwargs["env"]
    box.fs.write_bytes.assert_awaited_once_with("/gitedge/job.json", descriptor)
    box.create_process.assert_awaited_once()


async def test_docker_missing_container_cleanup_is_idempotent(mocker: MockerFixture) -> None:
    sdk = mocker.MagicMock()
    sdk.__aenter__.return_value = sdk
    sdk.containers.get = mocker.AsyncMock(side_effect=DockerError(404, "No such container"))
    mocker.patch("app.clients.sandboxes.Docker", return_value=sdk)
    await DockerSandboxClient("prepared").delete("absent")
    sdk.__aexit__.assert_awaited_once()
