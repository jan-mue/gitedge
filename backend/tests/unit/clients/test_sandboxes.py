from __future__ import annotations

import io
import json
import tarfile
from typing import TYPE_CHECKING

import pytest
from docker.errors import NotFound
from vercel.sandbox import SandboxStatus

from app.clients.sandboxes import DockerSandboxClient, SandboxError, VercelSandboxClient

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


async def test_docker_provisioning_does_not_pull_images_or_upload_source(mocker: MockerFixture) -> None:
    sdk = mocker.MagicMock()
    sdk.__enter__.return_value = sdk
    sdk.api.create_container.return_value = {"Id": "job-container"}
    mocker.patch("app.clients.sandboxes.docker.from_env", return_value=sdk)
    provider = DockerSandboxClient("prepared@sha256:abc")
    await provider.start("job", {"input.json": json.dumps({"job": "test"}).encode()}, 60)
    sdk.images.pull.assert_not_called()
    sdk.api.put_archive.assert_not_called()
    sdk.api.start.assert_called_once_with("job-container")
    assert sdk.api.create_container.call_args.args[0] == "prepared@sha256:abc"
    assert "source" not in sdk.api.create_container.call_args.kwargs["environment"]
    config = sdk.api.create_host_config.call_args.kwargs
    assert config["cap_drop"] == ["ALL"]
    assert not config["binds"]


async def test_vercel_uses_prepared_snapshot_and_never_receives_source(mocker: MockerFixture) -> None:
    box = mocker.MagicMock()
    box.create_process = mocker.AsyncMock()
    create = mocker.patch("app.clients.sandboxes.create_sandbox", new=mocker.AsyncMock(return_value=box))
    provider = VercelSandboxClient("prepared", "snapshot-123")
    await provider.start("job", {"input.json": b'{"job":"test"}'}, 60)
    kwargs = create.call_args.kwargs
    assert kwargs["persistent"] is False
    assert kwargs["image"] is None
    assert kwargs["source"].snapshot_id == "snapshot-123"
    assert set(kwargs["env"]) == {"GITEDGE_JOB", "GITEDGE_RESTORE_URL"}
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
    container = sdk.containers.get.return_value
    container.status = "running"
    expected = {"log.jsonl": b"hello\n", "result.json": b'{"status":"success"}', "exit-code": b"0"}
    finished = False

    def archive(path: str) -> tuple[list[bytes], dict[str, int]]:
        nonlocal finished
        name = path.rsplit("/", 1)[-1]
        if name == "exit-code":
            finished = True
        if name == "result.json" and not finished:
            raise NotFound("Job has not finished yet")
        if name not in expected:
            raise NotFound("No such file")
        data = expected[name]
        output = io.BytesIO()
        with tarfile.open(fileobj=output, mode="w") as tar:
            entry = tarfile.TarInfo(name)
            entry.size = len(data)
            tar.addfile(entry, io.BytesIO(data))
        return [output.getvalue()], {"size": len(data)}

    container.get_archive.side_effect = archive
    mocker.patch("app.clients.sandboxes.docker.from_env", return_value=sdk)
    snapshot = await DockerSandboxClient("prepared").inspect("job")
    assert snapshot.running
    assert snapshot.files == expected


async def test_vercel_refuses_job_time_image_preparation(mocker: MockerFixture) -> None:
    create = mocker.patch("app.clients.sandboxes.create_sandbox", new=mocker.AsyncMock())
    with pytest.raises(SandboxError, match="prepared before dispatch"):
        await VercelSandboxClient("unprepared-image").start("job", {"input.json": b"{}"}, 60)
    create.assert_not_called()
