from __future__ import annotations

import asyncio
import uuid
from typing import TYPE_CHECKING

import pytest

from app.clients.sandboxes import AbstractSandboxClient, SandboxError
from app.entities.actions import WorkflowRun
from app.exceptions import InvalidInputError, NotFoundError, WorkflowError
from app.schemas.workflow_events import PushEvent
from app.services.actions.service import ActionsService
from app.services.actions.workflows import instantiate_jobs
from app.services.authorization import AuthorizationService
from tests.unit.utils.actions import FakeActionsStore, FakeWorkflowCompiler, compiled_fixture

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

    from tests.unit.utils.fakes import FakeStores


async def test_ready_jobs_provision_concurrently_without_exceeding_the_limit(
    mocker: MockerFixture, fake_stores: FakeStores
) -> None:
    provider = mocker.AsyncMock(spec=AbstractSandboxClient)
    started: list[str] = []
    both_started = asyncio.Event()

    async def start(name: str, _files: dict[str, bytes], _lifetime: int) -> None:
        started.append(name)
        if len(started) == 2:
            both_started.set()
        await asyncio.wait_for(both_started.wait(), timeout=1)

    provider.start.side_effect = start
    store = FakeActionsStore()
    run = await store.add_run(
        WorkflowRun(
            id=uuid.uuid4(),
            repo_id=uuid.uuid4(),
            workflow=".gitedge/workflow/ci.yaml",
            definition="source retained for audit only",
            compiled=compiled_fixture("parallel").model_dump(mode="json", by_alias=True, exclude_none=True),
            event={"repository": {"full_name": "owner/repo"}},
            event_name="push",
            event_key="push-1",
            actor="owner",
            provider="docker",
            sha="a" * 40,
            ref="refs/heads/main",
            status="queued",
            jobs=[job.model_dump(mode="json") for job in instantiate_jobs(compiled_fixture("parallel"), 60)],
        )
    )
    service = ActionsService(
        store,
        mocker.Mock(),
        fake_stores.repository,
        fake_stores.blob,
        provider,
        compiler=FakeWorkflowCompiler(),
        authorization=mocker.AsyncMock(spec=AuthorizationService),
        provider="docker",
        max_timeout=60,
        max_parallel=2,
    )
    assert await service.scheduler.advance(run.repo_id, run.id)
    assert len(started) == 2
    assert [job["status"] for job in run.jobs] == ["running", "running", "queued"]


async def test_provisioning_failures_finish_out_of_order_dependencies_without_periodic_recovery(
    mocker: MockerFixture, fake_stores: FakeStores
) -> None:
    provider = mocker.AsyncMock(spec=AbstractSandboxClient)
    provider.start.side_effect = SandboxError("Prepared image is unavailable")
    store = FakeActionsStore()
    run = await store.add_run(
        WorkflowRun(
            id=uuid.uuid4(),
            repo_id=uuid.uuid4(),
            workflow=".gitedge/workflow/ci.yaml",
            definition="source retained for audit only",
            compiled=compiled_fixture("dependencies").model_dump(mode="json", by_alias=True, exclude_none=True),
            event={"repository": {"full_name": "owner/repo"}},
            event_name="push",
            event_key="push-1",
            actor="owner",
            provider="docker",
            sha="a" * 40,
            ref="refs/heads/main",
            status="queued",
            jobs=[job.model_dump(mode="json") for job in instantiate_jobs(compiled_fixture("dependencies"), 60)],
        )
    )
    service = ActionsService(
        store,
        mocker.Mock(),
        fake_stores.repository,
        fake_stores.blob,
        provider,
        compiler=FakeWorkflowCompiler(),
        authorization=mocker.AsyncMock(spec=AuthorizationService),
        provider="docker",
        max_timeout=60,
        max_parallel=1,
    )
    assert await service.scheduler.advance(run.repo_id, run.id)
    assert run.status == "failure"
    assert all(job["status"] == "failure" and job["sandbox"] is None for job in run.jobs)
    assert provider.start.await_count == 2
    assert provider.delete.await_count == 2


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
    service = ActionsService(
        store,
        repositories,
        repository_store,
        fake_stores.blob,
        mocker.AsyncMock(spec=AbstractSandboxClient),
        compiler=FakeWorkflowCompiler(),
        authorization=mocker.AsyncMock(spec=AuthorizationService),
        provider="docker",
        max_timeout=60,
        max_parallel=1,
        pull_requests=pulls,
    )
    checks = await service.pull_request_checks("owner", "repo", 1, None)
    assert checks.head_sha == "a" * 40
    assert len(checks.runs) == 1
    assert store.runs[checks.runs[0].id].event_key == "latest"
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
        authorization=mocker.AsyncMock(spec=AuthorizationService),
        provider="docker",
        max_timeout=60,
        max_parallel=1,
        pull_requests=pulls,
    )
    trigger = mocker.patch.object(service, "trigger", new_callable=mocker.AsyncMock)
    on_pull = mocker.patch.object(service, "on_pull_request", new_callable=mocker.AsyncMock)
    await service.on_push("owner", "repo", {"refs/heads/feature": "a" * 40}, {"refs/heads/feature": "b" * 40}, user)
    trigger.assert_awaited_once()
    on_pull.assert_awaited_once_with("owner", "repo", 7, "feature", "main", user, action="synchronize")


@pytest.mark.parametrize(
    "unreadable",
    [
        b"\xff",
        NotFoundError("Dangling workflow symlink"),
        WorkflowError("Workflow symlink must stay inside its repository"),
        InvalidInputError("Workflow target is not a file"),
        OSError("Cannot read workflow"),
    ],
)
async def test_unreadable_workflow_records_failure_without_aborting_other_workflows(
    mocker: MockerFixture, fake_stores: FakeStores, unreadable: bytes | Exception
) -> None:
    repository = mocker.Mock(
        id=uuid.uuid4(),
        is_private=False,
        default_branch="main",
        owner=mocker.Mock(display_name="Owner", principal_type="user"),
    )
    repository_store = mocker.AsyncMock()
    repository_store.get_by_owner_and_name.return_value = repository
    repositories = mocker.AsyncMock()
    paths = [".gitedge/workflow/bad.yaml", ".gitedge/workflow/good.yaml"]
    repositories.get_file_index.return_value = mocker.Mock(paths=paths)
    repositories.action_revision.return_value = ("a" * 40, "refs/heads/main")
    repositories.get_raw.side_effect = [unreadable, b"valid workflow"]
    store = FakeActionsStore()
    service = ActionsService(
        store,
        repositories,
        repository_store,
        fake_stores.blob,
        mocker.AsyncMock(spec=AbstractSandboxClient),
        compiler=FakeWorkflowCompiler(),
        authorization=mocker.AsyncMock(spec=AuthorizationService),
        provider="docker",
        max_timeout=60,
        max_parallel=1,
    )
    advance = mocker.patch.object(service.scheduler, "advance", new_callable=mocker.AsyncMock)
    await service.trigger("owner", "repo", "main", PushEvent(), actor="owner", event_key="push-1")
    runs = list(store.runs.values())
    assert [run.workflow for run in runs] == paths
    assert runs[0].status == "failure"
    assert runs[0].error
    assert runs[0].completed_at is not None
    assert runs[0].definition == ""
    assert runs[1].status == "queued"
    assert advance.await_count == 2
