from __future__ import annotations

import base64
import json
import secrets
import zlib
from typing import TYPE_CHECKING

import pytest
from aiodocker.exceptions import DockerError
from vercel.sandbox import SandboxStatus

from app.clients.sandboxes import DockerSandboxClient, SandboxError, VercelSandboxClient

if TYPE_CHECKING:
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
    assert "Binds" not in config["HostConfig"]
    assert "Volumes" not in config
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


async def test_checking_expired_vercel_sandbox_never_resumes_or_reads_it(mocker: MockerFixture) -> None:
    box = mocker.MagicMock(status=SandboxStatus.STOPPED)
    mocker.patch("app.clients.sandboxes.get_sandbox", new=mocker.AsyncMock(return_value=box))
    assert not await VercelSandboxClient("prepared").is_running("job")
    box.query_processes.assert_not_called()
    box.fs.read_bytes.assert_not_called()


@pytest.mark.parametrize("running", [True, False])
async def test_vercel_checks_only_process_liveness(mocker: MockerFixture, running: bool) -> None:
    box = mocker.MagicMock(status=SandboxStatus.RUNNING)
    box.query_processes = mocker.AsyncMock(return_value=[mocker.Mock(returncode=None if running else 0)])
    mocker.patch("app.clients.sandboxes.get_sandbox", new=mocker.AsyncMock(return_value=box))
    assert await VercelSandboxClient("prepared").is_running("job") == running
    box.fs.read_bytes.assert_not_called()


async def test_docker_liveness_never_downloads_an_archive(mocker: MockerFixture) -> None:
    sdk = mocker.MagicMock()
    sdk.__aenter__.return_value = sdk
    container = mocker.Mock()
    container.show = mocker.AsyncMock(return_value={"State": {"Status": "running"}})
    sdk.containers.get = mocker.AsyncMock(return_value=container)
    mocker.patch("app.clients.sandboxes.Docker", return_value=sdk)
    assert await DockerSandboxClient("prepared").is_running("job")
    container.get_archive.assert_not_called()


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
