from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from app.clients.sandboxes import AbstractSandboxClient
from app.entities.actions import WorkflowRun
from app.services.actions.service import ActionsService
from tests.unit.utils.actions import FakeActionsQueue, FakeActionsStore, FakeWorkflowCompiler

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

    from tests.unit.utils.fakes import FakeStores


async def test_pr_checks_follow_the_head_and_ignore_other_prs_and_old_deliveries(
    mocker: MockerFixture, fake_stores: FakeStores
) -> None:
    repository = mocker.Mock(id=uuid.uuid4(), owner_id=uuid.uuid4(), is_private=False)
    repository_store = mocker.AsyncMock()
    repository_store.get_by_owner_and_name.return_value = repository
    repositories = mocker.AsyncMock()
    repositories.action_revision.return_value = ("a" * 40, "refs/heads/feature")
    pulls = mocker.AsyncMock()
    pulls.get_by_number.return_value = mocker.Mock(head_branch="feature")
    store = FakeActionsStore()
    for sha, number, event_key in [
        ("b" * 40, 1, "old-head"),
        ("a" * 40, 1, "old-delivery"),
        ("a" * 40, 2, "other-pr"),
        ("a" * 40, 1, "latest"),
    ]:
        await store.add_run(
            WorkflowRun(
                id=uuid.uuid4(),
                repo_id=repository.id,
                workflow=".gitedge/workflow/ci.yaml",
                name="CI",
                definition="jobs: {}",
                event={"pull_request": {"number": number}},
                event_name="pull_request",
                event_key=event_key,
                actor="owner",
                provider="docker",
                sha=sha,
                ref="refs/heads/feature",
                status="success",
                jobs=[],
            )
        )
    sandbox = mocker.AsyncMock(spec=AbstractSandboxClient)
    queue = FakeActionsQueue()
    service = ActionsService(
        store,
        repositories,
        repository_store,
        fake_stores.blob,
        sandbox,
        compiler=FakeWorkflowCompiler(),
        queue=queue,
        provider="docker",
        max_timeout=60,
        max_parallel=1,
        pull_requests=pulls,
    )
    checks = await service.pull_request_checks("owner", "repo", 1, None)
    assert checks.head_sha == "a" * 40
    assert len(checks.runs) == 1
    assert store.runs[checks.runs[0].id].event_key == "latest"
    assert len(await service.list_runs("owner", "repo", None)) == 4
    sandbox.start.assert_not_awaited()
    sandbox.inspect.assert_not_awaited()
    sandbox.delete.assert_not_awaited()
    assert queue.deliveries == []
    assert queue.recoveries == 0
    repositories.action_revision.return_value = ("c" * 40, "refs/heads/feature")
    assert (await service.pull_request_checks("owner", "repo", 1, None)).runs == []


async def test_push_to_an_open_pr_triggers_synchronize(mocker: MockerFixture, fake_stores: FakeStores) -> None:
    repository = mocker.Mock(id=uuid.uuid4(), owner_id=uuid.uuid4(), is_private=False)
    user = mocker.Mock(id=repository.owner_id, is_superuser=False)
    repository_store = mocker.AsyncMock()
    repository_store.get_by_owner_and_name.return_value = repository
    repositories = mocker.AsyncMock()
    repositories.compare.return_value = mocker.Mock(files=[])
    pulls = mocker.AsyncMock()
    pulls.list_by_repo.return_value = [mocker.Mock(number=7, head_branch="feature", base_branch="main")]
    service = ActionsService(
        FakeActionsStore(),
        repositories,
        repository_store,
        fake_stores.blob,
        mocker.AsyncMock(spec=AbstractSandboxClient),
        compiler=FakeWorkflowCompiler(),
        queue=FakeActionsQueue(),
        provider="docker",
        max_timeout=60,
        max_parallel=1,
        pull_requests=pulls,
    )
    trigger = mocker.patch.object(service.events, "trigger", new_callable=mocker.AsyncMock)
    on_pull = mocker.patch.object(service.events, "on_pull_request", new_callable=mocker.AsyncMock)
    await service.on_push("owner", "repo", {"refs/heads/feature": "a" * 40}, {"refs/heads/feature": "b" * 40}, user)
    trigger.assert_awaited_once()
    on_pull.assert_awaited_once_with("owner", "repo", 7, "feature", "main", user, action="synchronize")
