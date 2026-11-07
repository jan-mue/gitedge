from __future__ import annotations

import asyncio
import json
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

from app.clients.sandboxes import AbstractSandboxClient, SandboxError, SandboxExecution
from app.entities.actions import WorkflowRun
from app.exceptions import ActionsUnavailableError, ConflictError, PermissionDeniedError
from app.services.actions.notifications import WorkflowFailureNotifications
from app.services.actions.service import ActionsService
from app.services.actions.workflows import instantiate_jobs
from app.services.authorization import AuthorizationService
from tests.unit.utils.actions import FakeActionsQueue, FakeActionsStore, FakeWorkflowCompiler, compiled_fixture

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from pytest_mock import AsyncMockType, MockerFixture

    from app.clients.actions import RunState
    from app.entities.actions import WorkflowOutbox
    from app.schemas.runners import LinuxRunner
    from tests.unit.utils.fakes import FakeStores

type Execution = tuple[ActionsService, FakeActionsStore, AsyncMockType, FakeActionsQueue]


@pytest.fixture
def execution(mocker: MockerFixture, fake_stores: FakeStores) -> Execution:
    store, queue = FakeActionsStore(), FakeActionsQueue()
    sandbox = mocker.AsyncMock(spec=AbstractSandboxClient)
    sandbox.status.return_value = SandboxExecution(True)
    service = ActionsService(
        store,
        mocker.Mock(),
        fake_stores.repository,
        fake_stores.blob,
        sandbox,
        compiler=FakeWorkflowCompiler(),
        authorization=mocker.AsyncMock(spec=AuthorizationService),
        notifications=mocker.AsyncMock(spec=WorkflowFailureNotifications),
        queue=queue,
        provider="docker",
        max_timeout=60,
        max_parallel=2,
    )
    return service, store, sandbox, queue


async def add_run(execution: Execution, fixture: str = "basic") -> WorkflowRun:
    service, store, _, _ = execution
    compiled = compiled_fixture(fixture)
    run = WorkflowRun(
        id=uuid.uuid4(),
        repo_id=uuid.uuid4(),
        workflow=".gitedge/workflow/ci.yaml",
        name="CI",
        definition="audit source",
        compiled=compiled.model_dump(mode="json", by_alias=True, exclude_none=True),
        event={"repository": {"full_name": "owner/repo"}},
        event_name="push",
        event_key=uuid.uuid4().hex,
        actor="owner",
        provider="docker",
        sha="a" * 40,
        ref="refs/heads/main",
        status="queued",
        jobs=[job.model_dump(mode="json") for job in instantiate_jobs(compiled, 60)],
    )
    await store.add_run(run, service.scheduler.advance)
    return run


def pending(store: FakeActionsStore, kind: str) -> list[WorkflowOutbox]:
    return [item for item in store.messages.values() if item.kind == kind and item.acknowledged_at is None]


def completion(sandbox: AsyncMockType) -> tuple[uuid.UUID, str, bytes]:
    descriptor = json.loads(sandbox.start.call_args.args[1]["input.json"])
    identity = descriptor["attempt"]
    payload = {
        "version": 1,
        **identity,
        "exit_code": 0,
        "last_seq": 0,
        "result": {"status": "success", "steps": {}, "outputs": {"value": "ready"}},
    }
    return uuid.UUID(identity["id"]), f"Bearer {descriptor['report_token']}", json.dumps(payload).encode()


async def observe_exit(execution: Execution, code: int = 0) -> None:
    service, store, sandbox, _ = execution
    sandbox.status.return_value = SandboxExecution(False, code)
    await service.dispatcher.deliver(min(pending(store, "inspect"), key=lambda item: item.due_at))


async def test_dispatch_claim_commits_before_provider_io_and_duplicate_deliveries_do_not_launch_again(
    execution: Execution,
) -> None:
    service, store, sandbox, _ = execution
    run = await add_run(execution, "parallel")
    started, both = [], asyncio.Event()

    async def start(name: str, files: dict[str, bytes], lifetime: int, *, runner: LinuxRunner) -> None:
        assert lifetime == 60
        assert not store.in_transaction
        payload = json.loads(files["input.json"])
        assert payload["version"] == 4
        assert payload["job"]["runner"] == runner
        assert name.endswith(payload["attempt"]["id"].replace("-", ""))
        started.append(name)
        if len(started) == 2:
            both.set()
        await asyncio.wait_for(both.wait(), 1)

    sandbox.start.side_effect = start
    commands = pending(store, "dispatch")
    assert len(commands) == 2
    assert not sandbox.start.called
    await asyncio.gather(*(service.dispatcher.deliver(command) for command in commands))
    await service.dispatcher.deliver(commands[0])
    assert sandbox.start.await_count == 2
    assert len(set(started)) == 2
    assert [job["status"] for job in run.jobs] == ["running", "running", "queued"]


async def test_lost_publish_is_recovered_from_the_committed_outbox(execution: Execution, mocker: MockerFixture) -> None:
    service, store, _, queue = execution
    run = await add_run(execution)
    command = pending(store, "dispatch")[0]
    publish = mocker.patch.object(queue, "publish", side_effect=ActionsUnavailableError("outage"))
    with pytest.raises(ActionsUnavailableError):
        await service.dispatcher.flush()
    assert run.id in store.runs
    assert command.published_at is None
    publish.side_effect = None
    await service.dispatcher.reconcile()
    assert command.published_at is not None
    assert publish.call_args.args[1].id == command.id


async def test_inspection_retry_resumes_its_lease_after_a_database_lock_failure(
    execution: Execution, mocker: MockerFixture
) -> None:
    service, store, sandbox, _ = execution
    run = await add_run(execution)
    await service.dispatcher.deliver(pending(store, "dispatch")[0])
    command = min(pending(store, "inspect"), key=lambda item: item.due_at)
    transaction = store.transaction
    calls = 0

    @asynccontextmanager
    async def fail_after_observation(
        run_id: uuid.UUID, repo_id: uuid.UUID | None = None
    ) -> AsyncGenerator[RunState | None]:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise ActionsUnavailableError("Workflow transition is busy")
        async with transaction(run_id, repo_id) as state:
            yield state

    mocker.patch.object(store, "transaction", side_effect=fail_after_observation)
    with pytest.raises(ActionsUnavailableError, match="Workflow transition is busy"):
        await service.dispatcher.deliver(command)
    assert command.attempt_id is not None
    attempt = store.attempts[command.attempt_id]
    assert attempt.lease_until is not None
    assert attempt.lease_until > datetime.now(UTC)
    other = next(item for item in pending(store, "inspect") if item.id != command.id)
    with pytest.raises(ActionsUnavailableError, match="Job operation is leased"):
        await service.dispatcher.deliver(other)
    assert sandbox.status.await_count == 1

    await service.dispatcher.deliver(command)

    assert sandbox.status.await_count == 2
    assert command.acknowledged_at is not None
    assert attempt.claim is None
    assert attempt.lease_until is None
    assert run.status == "running"


async def test_cancel_during_provisioning_revokes_callbacks_and_destroys_a_late_sandbox(execution: Execution) -> None:
    service, store, sandbox, _ = execution
    run = await add_run(execution)
    started, finish = asyncio.Event(), asyncio.Event()

    async def start(_name: str, _files: dict[str, bytes], _lifetime: int, *, runner: LinuxRunner) -> None:
        assert runner == "ubuntu-24.04"
        assert not store.in_transaction
        started.set()
        await finish.wait()

    sandbox.start.side_effect = start
    delivery = asyncio.create_task(service.dispatcher.deliver(pending(store, "dispatch")[0]))
    await asyncio.wait_for(started.wait(), 1)
    await service.dispatcher.cancel(run.repo_id, run.id)
    with pytest.raises(PermissionDeniedError):
        await service.complete(*completion(sandbox))
    finish.set()
    await delivery
    assert run.status == "cancelled"
    assert all(job["status"] == "cancelled" for job in run.jobs)
    sandbox.delete.assert_awaited()


async def test_expired_provisioning_is_retried_with_a_new_attempt_and_fence(execution: Execution) -> None:
    service, store, sandbox, _ = execution
    await add_run(execution)
    await service.dispatcher.deliver(pending(store, "dispatch")[0])
    old = next(iter(store.attempts.values()))
    token = completion(sandbox)
    old.status, old.lease_until = "starting", datetime.now(UTC) - timedelta(seconds=1)
    await service.dispatcher.reconcile()
    newest = max(store.attempts.values(), key=lambda attempt: attempt.generation)
    assert newest.generation == 2
    assert newest.fence != old.fence
    assert newest.sandbox != old.sandbox
    with pytest.raises(PermissionDeniedError):
        await service.complete(*token)


async def test_provisioning_retries_are_bounded_and_resources_are_cleaned(execution: Execution) -> None:
    service, store, sandbox, _ = execution
    run = await add_run(execution)
    sandbox.start.side_effect = SandboxError("provider failed")
    for _ in range(3):
        assert not pending(store, "notify")
        await service.dispatcher.deliver(pending(store, "dispatch")[0])
    for command in pending(store, "cleanup"):
        await service.dispatcher.deliver(command)
    assert sandbox.start.await_count == sandbox.delete.await_count == 3
    assert run.status == "failure"
    assert run.jobs[0]["sandbox"] is None
    assert [attempt.generation for attempt in store.attempts.values()] == [1, 2, 3]
    assert len(pending(store, "notify")) == 1


async def test_completion_push_is_idempotent_and_never_inspects_files(execution: Execution) -> None:
    service, store, sandbox, _ = execution
    run = await add_run(execution)
    await service.dispatcher.deliver(pending(store, "dispatch")[0])
    await service.complete(*completion(sandbox))
    await service.complete(*completion(sandbox))
    assert run.status == "running"
    assert not pending(store, "cleanup")
    await observe_exit(execution)
    await service.dispatcher.deliver(pending(store, "cleanup")[0])
    sandbox.status.assert_awaited_once()
    assert run.status == "success"
    assert run.jobs[0]["outputs"] == {"value": "ready"}


async def test_late_collection_cannot_resurrect_a_cancelled_attempt(execution: Execution) -> None:
    service, store, sandbox, _ = execution
    run = await add_run(execution)
    await service.dispatcher.deliver(pending(store, "dispatch")[0])
    started, finish = asyncio.Event(), asyncio.Event()

    async def status(_name: str) -> SandboxExecution:
        assert not store.in_transaction
        started.set()
        await finish.wait()
        return SandboxExecution(False, 0)

    sandbox.status.side_effect = status
    command = next(item for item in pending(store, "inspect") if item.due_at < datetime.now(UTC) + timedelta(seconds=1))
    delivery = asyncio.create_task(service.dispatcher.deliver(command))
    await asyncio.wait_for(started.wait(), 1)
    await service.dispatcher.cancel(run.repo_id, run.id)
    finish.set()
    await delivery
    assert run.status == "cancelled"
    assert run.jobs[0]["outputs"] == {}
    assert next(iter(store.attempts.values())).status == "cancelled"


async def test_expired_job_deadline_enqueues_cleanup_without_a_new_generation(execution: Execution) -> None:
    service, store, _, _ = execution
    run = await add_run(execution)
    await service.dispatcher.deliver(pending(store, "dispatch")[0])
    attempt = next(iter(store.attempts.values()))
    attempt.deadline = datetime.now(UTC) - timedelta(seconds=1)
    command = next(item for item in pending(store, "inspect") if item.due_at < datetime.now(UTC) + timedelta(seconds=1))
    await service.dispatcher.deliver(command)
    await service.dispatcher.deliver(pending(store, "cleanup")[0])
    assert run.status == "failure"
    assert run.jobs[0]["error"] == "Job exceeded timeout-minutes"
    assert len(store.attempts) == 1


async def test_recovery_fails_legacy_execution_visibly_and_cleans_its_handle(execution: Execution) -> None:
    service, store, sandbox, _ = execution
    run = await add_run(execution)
    legacy = run.jobs[0]
    legacy["attempt_id"], legacy["sandbox"] = None, "legacy-job"
    store.attempts.clear()
    store.messages.clear()
    await service.dispatcher.reconcile()
    await service.dispatcher.deliver(pending(store, "cleanup")[0])
    assert run.status == "failure"
    assert "Legacy execution" in run.jobs[0]["error"]
    sandbox.delete.assert_awaited_once_with("legacy-job")
    sandbox.start.assert_not_awaited()


async def test_artifact_upload_commits_a_fenced_reference_before_completion(
    execution: Execution,
    fake_stores: FakeStores,
    mocker: MockerFixture,
) -> None:
    service, store, sandbox, _ = execution
    run = await add_run(execution)
    await service.dispatcher.deliver(pending(store, "dispatch")[0])
    attempt_id, authorization, result = completion(sandbox)
    original = fake_stores.blob.put

    async def put(key: str, payload: bytes) -> None:
        assert not store.in_transaction
        await original(key, payload)

    mocker.patch.object(fake_stores.blob, "put", side_effect=put)
    await service.publish_state(attempt_id, authorization, b"archive")
    await service.publish_state(attempt_id, authorization, b"archive")
    with pytest.raises(ConflictError):
        await service.publish_state(attempt_id, authorization, b"changed archive")
    await service.complete(attempt_id, authorization, result)
    await observe_exit(execution)
    key = store.attempts[attempt_id].artifact_key
    assert key is not None
    assert fake_stores.blob.objects[key] == b"archive"
    assert await store.artifacts(run.id) == [key]


async def test_matrix_runner_selection_reaches_the_provider(execution: Execution) -> None:
    service, store, sandbox, _ = execution
    await add_run(execution, "linux")
    for command in pending(store, "dispatch"):
        await service.dispatcher.deliver(command)
    assert [call.kwargs["runner"] for call in sandbox.start.call_args_list] == ["ubuntu-22.04", "ubuntu-24.04"]
    for call in sandbox.start.call_args_list:
        descriptor = json.loads(call.args[1]["input.json"])
        assert descriptor["job"]["runner"] == call.kwargs["runner"]


async def test_queued_old_manifests_fail_visibly_without_provisioning(execution: Execution) -> None:
    service, store, sandbox, _ = execution
    run = await add_run(execution)
    assert run.compiled is not None
    run.compiled["version"] = 1
    await service.dispatcher.deliver(pending(store, "dispatch")[0])
    assert run.jobs[0]["status"] == "failure"
    assert "incompatible compiled manifest" in run.jobs[0]["error"]
    sandbox.start.assert_not_awaited()


async def test_early_completion_cannot_release_dependencies_while_launcher_runs(execution: Execution) -> None:
    service, store, sandbox, _ = execution
    run = await add_run(execution, "dependencies")
    await service.dispatcher.deliver(pending(store, "dispatch")[0])
    await service.complete(*completion(sandbox))
    await service.dispatcher.deliver(min(pending(store, "inspect"), key=lambda item: item.due_at))
    assert next(job for job in run.jobs if job["key"] == "parent")["status"] == "running"
    assert next(job for job in run.jobs if job["key"] == "dependent")["status"] == "queued"
    assert not pending(store, "cleanup")
    await observe_exit(execution)
    assert next(job for job in run.jobs if job["key"] == "parent")["status"] == "success"
    assert next(job for job in run.jobs if job["key"] == "dependent")["status"] == "queued"


async def test_provider_exit_code_overrides_forged_success(execution: Execution) -> None:
    service, store, sandbox, _ = execution
    run = await add_run(execution)
    await service.dispatcher.deliver(pending(store, "dispatch")[0])
    await service.complete(*completion(sandbox))
    await observe_exit(execution, 17)
    assert run.jobs[0]["status"] == "failure"
    assert run.jobs[0]["error"] == "Job bootstrap exited unsuccessfully"


async def test_report_retry_cannot_replace_the_first_result(execution: Execution) -> None:
    service, store, sandbox, _ = execution
    await add_run(execution)
    await service.dispatcher.deliver(pending(store, "dispatch")[0])
    attempt_id, authorization, raw = completion(sandbox)
    await service.complete(attempt_id, authorization, raw)
    report = json.loads(raw)
    report["result"]["outputs"] = {"changed": "true"}
    with pytest.raises(ConflictError):
        await service.complete(attempt_id, authorization, json.dumps(report).encode())


async def test_pull_request_jobs_receive_no_repository_secrets_or_shared_cache(execution: Execution) -> None:
    service, store, sandbox, _ = execution
    run = await add_run(execution)
    run.event_name = "pull_request"
    run.event["pull_request"] = {"number": 1}
    service.dispatcher.secrets[str(run.repo_id)] = {"PRODUCTION_TOKEN": "should-not-reach-the-job"}
    await service.dispatcher.deliver(pending(store, "dispatch")[0])
    descriptor = json.loads(sandbox.start.call_args.args[1]["input.json"])
    assert set(descriptor["secrets"]) == {"GITHUB_TOKEN"}
    assert "cache_url" not in descriptor
