from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

from app.clients.sandboxes import AbstractSandboxClient, SandboxError, SandboxSnapshot
from app.entities.actions import WorkflowRun
from app.services.actions.scheduler import RunScheduler
from app.services.actions.workflows import instantiate_jobs
from tests.unit.utils.actions import FakeActionsStore, compiled_fixture

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

    from tests.unit.utils.fakes import FakeStores


@pytest.fixture
async def scheduled_run(
    mocker: MockerFixture, fake_stores: FakeStores
) -> tuple[RunScheduler, FakeActionsStore, WorkflowRun]:
    store = FakeActionsStore()
    compiled = compiled_fixture()
    run = await store.add_run(
        WorkflowRun(
            id=uuid.uuid4(),
            repo_id=uuid.uuid4(),
            workflow=".gitedge/workflow/ci.yaml",
            definition="source retained for audit only",
            compiled=compiled.model_dump(mode="json", by_alias=True, exclude_none=True),
            event={"repository": {"full_name": "owner/repo"}},
            event_name="push",
            event_key="push-1",
            actor="owner",
            provider="docker",
            sha="a" * 40,
            ref="refs/heads/main",
            status="queued",
            jobs=[job.model_dump(mode="json") for job in instantiate_jobs(compiled, 60)],
        )
    )
    provider = mocker.AsyncMock(spec=AbstractSandboxClient)
    provider.inspect.return_value = SandboxSnapshot(running=True)
    return RunScheduler(store, fake_stores.blob, provider, 1, {}), store, run


async def test_provider_and_blob_io_never_hold_the_run_lock(
    mocker: MockerFixture, scheduled_run: tuple[RunScheduler, FakeActionsStore, WorkflowRun]
) -> None:
    scheduler, store, run = scheduled_run

    async def start(_name: str, _files: dict[str, bytes], _lifetime: int) -> None:
        assert not store.locked_runs

    async def inspect(_name: str) -> SandboxSnapshot:
        assert not store.locked_runs
        return SandboxSnapshot(
            running=False,
            files={"result.json": b'{"status":"success"}', "exit-code": b"0", "state.tar.gz": b"state"},
        )

    async def put(_key: str, _data: bytes) -> str:
        assert not store.locked_runs
        return "version"

    async def delete(_name: str) -> None:
        assert not store.locked_runs

    mocker.patch.object(scheduler.sandbox, "start", side_effect=start)
    mocker.patch.object(scheduler.sandbox, "inspect", side_effect=inspect)
    mocker.patch.object(scheduler.blobs, "put", side_effect=put)
    cleanup = mocker.patch.object(scheduler.sandbox, "delete", side_effect=delete)
    assert await scheduler.advance(run.repo_id, run.id)
    assert await scheduler.advance(run.repo_id, run.id)
    assert run.status == "success"
    assert run.jobs[0]["sandbox"] is None
    assert "_operation" not in run.jobs[0]
    cleanup.assert_awaited_once()


async def test_completion_during_slow_launch_does_not_collide_or_launch_twice(
    mocker: MockerFixture, scheduled_run: tuple[RunScheduler, FakeActionsStore, WorkflowRun]
) -> None:
    scheduler, store, run = scheduled_run
    entered = asyncio.Event()
    release = asyncio.Event()

    async def start(_name: str, _files: dict[str, bytes], _lifetime: int) -> None:
        assert not store.locked_runs
        entered.set()
        await asyncio.wait_for(release.wait(), timeout=1)

    launch = mocker.patch.object(scheduler.sandbox, "start", side_effect=start)
    inspect = mocker.patch.object(scheduler.sandbox, "inspect", return_value=SandboxSnapshot(running=True))
    first = asyncio.create_task(scheduler.advance(run.repo_id, run.id))
    try:
        await asyncio.wait_for(entered.wait(), timeout=1)
        assert await scheduler.advance(run.repo_id, run.id)
        launch.assert_awaited_once()
        inspect.assert_not_awaited()
    finally:
        release.set()
        assert await first
    assert run.jobs[0]["status"] == "running"
    assert "_operation" not in run.jobs[0]
    inspect.assert_awaited_once()


async def test_callback_racing_a_live_inspection_is_rechecked_without_losing_completion(
    mocker: MockerFixture, scheduled_run: tuple[RunScheduler, FakeActionsStore, WorkflowRun]
) -> None:
    scheduler, _store, run = scheduled_run
    await scheduler.advance(run.repo_id, run.id)
    entered = asyncio.Event()
    release = asyncio.Event()
    calls = 0

    async def inspect(_name: str) -> SandboxSnapshot:
        nonlocal calls
        calls += 1
        if calls == 1:
            entered.set()
            await asyncio.wait_for(release.wait(), timeout=1)
            return SandboxSnapshot(running=True)
        return SandboxSnapshot(running=False, files={"result.json": b'{"status":"success"}', "exit-code": b"0"})

    mocker.patch.object(scheduler.sandbox, "inspect", side_effect=inspect)
    first = asyncio.create_task(scheduler.advance(run.repo_id, run.id))
    try:
        await asyncio.wait_for(entered.wait(), timeout=1)
        assert await scheduler.advance(run.repo_id, run.id)
    finally:
        release.set()
        assert await first
    assert calls == 2
    assert run.status == "success"
    assert run.jobs[0]["sandbox"] is None


async def test_cancellation_wins_over_an_inflight_launch_and_cleans_up_afterward(
    mocker: MockerFixture, scheduled_run: tuple[RunScheduler, FakeActionsStore, WorkflowRun]
) -> None:
    scheduler, _store, run = scheduled_run
    entered = asyncio.Event()
    release = asyncio.Event()

    async def start(_name: str, _files: dict[str, bytes], _lifetime: int) -> None:
        entered.set()
        await asyncio.wait_for(release.wait(), timeout=1)

    mocker.patch.object(scheduler.sandbox, "start", side_effect=start)
    cleanup = mocker.patch.object(scheduler.sandbox, "delete")
    first = asyncio.create_task(scheduler.advance(run.repo_id, run.id))
    try:
        await asyncio.wait_for(entered.wait(), timeout=1)
        assert await scheduler.cancel(run.repo_id, run.id)
        assert run.status == "cancelled"
        cleanup.assert_not_awaited()
    finally:
        release.set()
        assert await first
    assert run.status == "cancelled"
    assert run.jobs[0]["status"] == "cancelled"
    assert run.jobs[0]["sandbox"] is None
    cleanup.assert_awaited_once()


async def test_expired_launch_claim_is_recovered_using_the_same_sandbox_name(
    mocker: MockerFixture, scheduled_run: tuple[RunScheduler, FakeActionsStore, WorkflowRun]
) -> None:
    scheduler, _store, run = scheduled_run
    sandbox = f"gitedge-job-{run.jobs[0]['id']}"
    run.jobs[0].update(
        status="running",
        sandbox=sandbox,
        _operation={
            "id": "abandoned",
            "kind": "start",
            "expires_at": (datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
        },
    )
    launch = mocker.patch.object(scheduler.sandbox, "start")
    assert await scheduler.advance(run.repo_id, run.id)
    assert launch.call_args.args[0] == sandbox
    assert "_operation" not in run.jobs[0]


async def test_cleanup_failure_is_retried_on_the_next_advance_not_in_a_busy_loop(
    mocker: MockerFixture, scheduled_run: tuple[RunScheduler, FakeActionsStore, WorkflowRun]
) -> None:
    scheduler, _store, run = scheduled_run
    run.status = "running"
    run.jobs[0].update(status="success", sandbox="sandbox")
    cleanup = mocker.patch.object(scheduler.sandbox, "delete", side_effect=SandboxError("Provider unavailable"))
    assert await scheduler.advance(run.repo_id, run.id)
    cleanup.assert_awaited_once()
    assert run.status == "running"
    assert run.jobs[0]["sandbox"] == "sandbox"
    cleanup.side_effect = None
    assert await scheduler.advance(run.repo_id, run.id)
    assert run.status == "success"
    assert run.jobs[0]["sandbox"] is None


async def test_run_with_no_remaining_jobs_finishes_without_claiming_provider_work(
    mocker: MockerFixture, scheduled_run: tuple[RunScheduler, FakeActionsStore, WorkflowRun]
) -> None:
    scheduler, _store, run = scheduled_run
    run.jobs = []
    launch = mocker.patch.object(scheduler.sandbox, "start")
    assert await scheduler.advance(run.repo_id, run.id)
    assert run.status == "success"
    assert run.completed_at is not None
    launch.assert_not_awaited()
