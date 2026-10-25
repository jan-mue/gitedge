from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import HTTPException

from app.clients.sandboxes import AbstractSandboxClient, SandboxError, SandboxSnapshot
from app.entities.actions import WorkflowRun
from app.exceptions import ActionsUnavailableError
from app.services.actions.service import ActionsService
from app.services.actions.workflows import instantiate_jobs
from tests.unit.utils.actions import FakeActionsQueue, FakeActionsStore, FakeWorkflowCompiler, compiled_fixture

if TYPE_CHECKING:
    from pytest_mock import AsyncMockType, MockerFixture

    from app.entities.actions import WorkflowOutbox
    from tests.unit.utils.fakes import FakeStores

type Execution = tuple[ActionsService, FakeActionsStore, AsyncMockType, FakeActionsQueue]


@pytest.fixture
def execution(mocker: MockerFixture, fake_stores: FakeStores) -> Execution:
    store, queue = FakeActionsStore(), FakeActionsQueue()
    sandbox = mocker.AsyncMock(spec=AbstractSandboxClient)
    sandbox.inspect.return_value = SandboxSnapshot(running=True)
    service = ActionsService(
        store,
        mocker.Mock(),
        fake_stores.repository,
        fake_stores.blob,
        sandbox,
        compiler=FakeWorkflowCompiler(),
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


def completion(sandbox: AsyncMockType) -> str:
    descriptor = json.loads(sandbox.start.call_args.args[1]["input.json"])
    return parse_qs(urlparse(descriptor["complete_url"]).query)["token"][0]


async def test_dispatch_claim_commits_before_provider_io_and_duplicate_deliveries_do_not_launch_again(
    execution: Execution,
) -> None:
    service, store, sandbox, _ = execution
    run = await add_run(execution, "parallel")
    started, both = [], asyncio.Event()

    async def start(name: str, files: dict[str, bytes], lifetime: int) -> None:
        assert lifetime == 60
        assert not store.in_transaction
        payload = json.loads(files["input.json"])
        assert payload["version"] == 2
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


async def test_cancel_during_provisioning_revokes_callbacks_and_destroys_a_late_sandbox(execution: Execution) -> None:
    service, store, sandbox, _ = execution
    run = await add_run(execution)
    started, finish = asyncio.Event(), asyncio.Event()

    async def start(_name: str, _files: dict[str, bytes], _lifetime: int) -> None:
        assert not store.in_transaction
        started.set()
        await finish.wait()

    sandbox.start.side_effect = start
    delivery = asyncio.create_task(service.dispatcher.deliver(pending(store, "dispatch")[0]))
    await started.wait()
    await service.dispatcher.cancel(run.repo_id, run.id)
    with pytest.raises(HTTPException) as rejected:
        await service.complete(completion(sandbox))
    assert rejected.value.status_code == 403
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
    with pytest.raises(HTTPException) as rejected:
        await service.complete(token)
    assert rejected.value.status_code == 403


async def test_provisioning_retries_are_bounded_and_resources_are_cleaned(execution: Execution) -> None:
    service, store, sandbox, _ = execution
    run = await add_run(execution)
    sandbox.start.side_effect = SandboxError("provider failed")
    for _ in range(3):
        await service.dispatcher.deliver(pending(store, "dispatch")[0])
    for command in pending(store, "cleanup"):
        await service.dispatcher.deliver(command)
    assert sandbox.start.await_count == sandbox.delete.await_count == 3
    assert run.status == "failure"
    assert run.jobs[0]["sandbox"] is None
    assert [attempt.generation for attempt in store.attempts.values()] == [1, 2, 3]


async def test_collection_is_outside_transactions_and_duplicate_completion_is_idempotent(execution: Execution) -> None:
    service, store, sandbox, _ = execution
    run = await add_run(execution)
    await service.dispatcher.deliver(pending(store, "dispatch")[0])
    descriptor = json.loads(sandbox.start.call_args.args[1]["input.json"])

    async def inspect(_name: str) -> SandboxSnapshot:
        assert not store.in_transaction
        return SandboxSnapshot(
            running=False,
            files={
                "exit-code": b"0",
                "result.json": json.dumps(
                    {"attempt": descriptor["attempt"], "status": "success", "steps": {}, "outputs": {"value": "ready"}}
                ).encode(),
                "log.jsonl": b"",
            },
        )

    sandbox.inspect.side_effect = inspect
    command = next(item for item in pending(store, "inspect") if item.due_at < datetime.now(UTC) + timedelta(seconds=1))
    await service.dispatcher.deliver(command)
    await service.dispatcher.deliver(command)
    await service.dispatcher.deliver(pending(store, "cleanup")[0])
    assert sandbox.inspect.await_count == 1
    assert run.status == "success"
    assert run.jobs[0]["outputs"] == {"value": "ready"}


async def test_late_collection_cannot_resurrect_a_cancelled_attempt(execution: Execution) -> None:
    service, store, sandbox, _ = execution
    run = await add_run(execution)
    await service.dispatcher.deliver(pending(store, "dispatch")[0])
    descriptor = json.loads(sandbox.start.call_args.args[1]["input.json"])
    started, finish = asyncio.Event(), asyncio.Event()

    async def inspect(_name: str) -> SandboxSnapshot:
        started.set()
        await finish.wait()
        return SandboxSnapshot(
            running=False,
            files={
                "exit-code": b"0",
                "result.json": json.dumps(
                    {"attempt": descriptor["attempt"], "status": "success", "outputs": {"late": "value"}}
                ).encode(),
            },
        )

    sandbox.inspect.side_effect = inspect
    command = next(item for item in pending(store, "inspect") if item.due_at < datetime.now(UTC) + timedelta(seconds=1))
    delivery = asyncio.create_task(service.dispatcher.deliver(command))
    await started.wait()
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
