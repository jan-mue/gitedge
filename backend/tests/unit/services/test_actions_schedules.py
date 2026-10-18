"""Scheduled CI must not inherit authority from anonymous Git writes."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from app.services.actions.service import ActionsService

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


@pytest.mark.parametrize("trusted", [None, b"other-commit", b"trusted-commit"])
async def test_schedules_only_execute_the_authenticated_revision(mocker: MockerFixture, trusted: bytes | None) -> None:
    repository = SimpleNamespace(id=uuid.uuid4(), owner=SimpleNamespace(name="owner"), name="repository")
    repositories = mocker.Mock()
    repositories.get_file_index = mocker.AsyncMock(
        return_value=SimpleNamespace(paths=[".gitedge/workflow/schedule.yaml"])
    )
    repositories.action_revision = mocker.AsyncMock(return_value=("trusted-commit", "refs/heads/main"))
    repositories.get_raw = mocker.AsyncMock(
        return_value=b"on:\n  schedule:\n    - cron: '* * * * *'\njobs:\n  test:\n    steps:\n      - run: echo hello\n"
    )
    repository_store = mocker.Mock()
    repository_store.get_all = mocker.AsyncMock(return_value=[repository])
    blobs = mocker.Mock()
    blobs.get_current = mocker.AsyncMock(return_value=trusted)
    service = ActionsService(
        mocker.Mock(), repositories, repository_store, blobs, {}, provider="docker", max_timeout=60, max_parallel=1
    )
    trigger = mocker.patch.object(service, "trigger", new=mocker.AsyncMock())
    await service.scheduled_workflows()
    if trusted == b"trusted-commit":
        trigger.assert_awaited_once()
        call = trigger.await_args
        assert call is not None
        assert call.args[2] == "trusted-commit"
        assert call.args[4]["ref"] == "refs/heads/main"
        repositories.get_raw.assert_awaited_once_with(
            "owner", "repository", "trusted-commit", ".gitedge/workflow/schedule.yaml"
        )
    else:
        trigger.assert_not_awaited()
        repositories.get_raw.assert_not_awaited()
