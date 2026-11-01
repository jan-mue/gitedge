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
from app.schemas.runners import LinuxRunner, RunnerImage

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


@pytest.fixture
def images() -> dict[LinuxRunner, RunnerImage]:
    return {
        "ubuntu-22.04": RunnerImage(image="prepared-22@sha256:abc"),
        "ubuntu-24.04": RunnerImage(image="prepared-24@sha256:def"),
        "ubuntu-26.04": RunnerImage(image="prepared-26@sha256:ghi"),
    }


@pytest.mark.parametrize("runner", ["ubuntu-22.04", "ubuntu-24.04", "ubuntu-26.04"])
async def test_docker_provisioning_does_not_pull_images_or_upload_source(
    mocker: MockerFixture, images: dict[LinuxRunner, RunnerImage], runner: LinuxRunner
) -> None:
    sdk = mocker.MagicMock()
    sdk.__aenter__.return_value = sdk
    container = mocker.Mock()
    container.start = mocker.AsyncMock()
    sdk.containers.create = mocker.AsyncMock(return_value=container)
    mocker.patch("app.clients.sandboxes.Docker", return_value=sdk)
    await DockerSandboxClient(images).start("job", {"input.json": b'{"job":"test"}'}, 60, runner=runner)
    sdk.images.pull.assert_not_called()
    container.start.assert_awaited_once()
    config = sdk.containers.create.call_args.kwargs["config"]
    assert config["Image"] == images[runner].image
    assert config["HostConfig"]["CapDrop"] == ["ALL"]
    assert "Binds" not in config["HostConfig"]
    assert "Volumes" not in config
    assert not any(value.startswith("source=") for value in config["Env"])
    sdk.__aexit__.assert_awaited_once()


async def test_vercel_uses_prepared_snapshot_and_never_receives_source(
    mocker: MockerFixture, images: dict[LinuxRunner, RunnerImage]
) -> None:
    box = mocker.MagicMock()
    box.create_process = mocker.AsyncMock()
    create = mocker.patch("app.clients.sandboxes.create_sandbox", new=mocker.AsyncMock(return_value=box))
    images["ubuntu-24.04"].snapshot_id = "snapshot-123"
    provider = VercelSandboxClient(images, region="iad1")
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


async def test_checking_expired_vercel_sandbox_never_resumes_or_reads_it(
    mocker: MockerFixture, images: dict[LinuxRunner, RunnerImage]
) -> None:
    box = mocker.MagicMock(status=SandboxStatus.STOPPED)
    mocker.patch("app.clients.sandboxes.get_sandbox", new=mocker.AsyncMock(return_value=box))
    assert not await VercelSandboxClient(images).is_running("job")
    box.query_processes.assert_not_called()
    box.fs.read_bytes.assert_not_called()


@pytest.mark.parametrize("running", [True, False])
async def test_vercel_checks_only_process_liveness(
    mocker: MockerFixture, images: dict[LinuxRunner, RunnerImage], running: bool
) -> None:
    box = mocker.MagicMock(status=SandboxStatus.RUNNING)
    box.query_processes = mocker.AsyncMock(return_value=[mocker.Mock(returncode=None if running else 0)])
    mocker.patch("app.clients.sandboxes.get_sandbox", new=mocker.AsyncMock(return_value=box))
    assert await VercelSandboxClient(images).is_running("job") == running
    box.fs.read_bytes.assert_not_called()


async def test_docker_liveness_never_downloads_an_archive(
    mocker: MockerFixture, images: dict[LinuxRunner, RunnerImage]
) -> None:
    sdk = mocker.MagicMock()
    sdk.__aenter__.return_value = sdk
    container = mocker.Mock()
    container.show = mocker.AsyncMock(return_value={"State": {"Status": "running"}})
    sdk.containers.get = mocker.AsyncMock(return_value=container)
    mocker.patch("app.clients.sandboxes.Docker", return_value=sdk)
    assert await DockerSandboxClient(images).is_running("job")
    container.get_archive.assert_not_called()


async def test_unconfigured_runner_fails_before_provisioning(mocker: MockerFixture) -> None:
    create = mocker.patch("app.clients.sandboxes.create_sandbox", new=mocker.AsyncMock())
    with pytest.raises(SandboxError, match="no configured image"):
        await VercelSandboxClient({}).start("job", {"input.json": b"{}"}, 60)
    create.assert_not_called()


async def test_vercel_uploads_only_the_descriptor_when_it_exceeds_the_environment_limit(
    mocker: MockerFixture, images: dict[LinuxRunner, RunnerImage]
) -> None:
    box = mocker.MagicMock()
    box.create_process = mocker.AsyncMock()
    box.fs.write_bytes = mocker.AsyncMock()
    create = mocker.patch("app.clients.sandboxes.create_sandbox", new=mocker.AsyncMock(return_value=box))
    descriptor = json.dumps({"job": "test", "value": secrets.token_hex(8192)}).encode()
    await VercelSandboxClient(images).start("job", {"input.json": descriptor}, 60)
    assert "GITEDGE_JOB" not in create.call_args.kwargs["env"]
    box.fs.write_bytes.assert_awaited_once_with("/gitedge/job.json", descriptor)
    box.create_process.assert_awaited_once()


async def test_docker_missing_container_cleanup_is_idempotent(
    mocker: MockerFixture, images: dict[LinuxRunner, RunnerImage]
) -> None:
    sdk = mocker.MagicMock()
    sdk.__aenter__.return_value = sdk
    sdk.containers.get = mocker.AsyncMock(side_effect=DockerError(404, "No such container"))
    mocker.patch("app.clients.sandboxes.Docker", return_value=sdk)
    await DockerSandboxClient(images).delete("absent")
    sdk.__aexit__.assert_awaited_once()


@pytest.mark.parametrize("runner", ["ubuntu-22.04", "ubuntu-24.04", "ubuntu-26.04"])
async def test_vercel_starts_the_requested_vcr_image_without_a_snapshot(
    mocker: MockerFixture, images: dict[LinuxRunner, RunnerImage], runner: LinuxRunner
) -> None:
    box = mocker.MagicMock()
    box.create_process = mocker.AsyncMock()
    create = mocker.patch("app.clients.sandboxes.create_sandbox", new=mocker.AsyncMock(return_value=box))
    await VercelSandboxClient(images).start("job", {"input.json": b"{}"}, 60, runner=runner)
    assert create.call_args.kwargs["image"] == images[runner].image
    assert create.call_args.kwargs["source"] is None
    box.create_process.assert_awaited_once()
