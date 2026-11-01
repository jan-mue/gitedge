from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING

import pytest
from app.exceptions import PermissionDeniedError, ConflictError

from app.exceptions import ActionsUnavailableError
from app.schemas.action_logs import LogChunk, LogRecord
from app.services.actions.logs import ActionsLogService
from tests.unit.services.test_actions_dispatch import (
    Execution,
    add_run,
    completion,
    pending,
)
from tests.unit.services.test_actions_dispatch import execution as execution  # noqa: PLC0414 — pytest fixture re-export
from tests.unit.utils.actions import FakeActionsLogStore

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

    from app.entities.actions import WorkflowRun
    from tests.unit.utils.fakes import FakeStores


type Reporting = tuple[ActionsLogService, FakeActionsLogStore, WorkflowRun]


@pytest.fixture
async def reporting(
    execution: Execution, fake_stores: FakeStores
) -> tuple[ActionsLogService, FakeActionsLogStore, WorkflowRun]:
    service, store, _, _ = execution
    run = await add_run(execution)
    await service.dispatcher.deliver(pending(store, "dispatch")[0])
    indexes = FakeActionsLogStore(store)
    logs = ActionsLogService(
        store, indexes, fake_stores.blob, fake_stores.redis, {str(run.repo_id): {"TOKEN": "secret-value"}}
    )
    return logs, indexes, run


def chunk(execution: Execution, start: int, messages: list[str]) -> LogChunk:
    descriptor = json.loads(execution[2].start.call_args.args[1]["input.json"])
    return LogChunk(
        **descriptor["attempt"],
        from_seq=start,
        to_seq=start + len(messages) - 1,
        records=[LogRecord(seq=start + offset, msg=msg, step_id="hello") for offset, msg in enumerate(messages)],
    )


async def upload(execution: Execution, logs: ActionsLogService, data: LogChunk) -> int:
    attempt_id, authorization, _ = completion(execution[2])
    return await logs.upload(attempt_id, authorization, data.model_dump_json().encode())


async def test_chunks_archive_before_ack_and_duplicate_delivery_preserves_one_index(
    execution: Execution,
    reporting: Reporting,
    fake_stores: FakeStores,
) -> None:
    logs, indexes, run = reporting
    data = chunk(execution, 1, ["<script>secret-value</script>", "done"])
    assert await upload(execution, logs, data) == 2
    assert await upload(execution, logs, data) == 2
    assert len(indexes.indexes) == len(fake_stores.blob.objects) == 1
    index = next(iter(indexes.indexes.values()))
    assert b"secret-value" not in fake_stores.blob.objects[index.object_key]
    assert len(execution[1].runs[run.id].jobs[0]) < 30
    assert "log" not in run.jobs[0]
    page = await logs.page(run.repo_id, run.id, data.id, 0)
    assert [item.msg for item in page.records] == ["<script>***</script>", "done"]
    assert page.next_seq == 2
    assert not page.complete


async def test_changed_retry_and_missing_sequences_are_rejected(execution: Execution, reporting: Reporting) -> None:
    logs, indexes, _ = reporting
    await upload(execution, logs, chunk(execution, 1, ["first"]))
    for data in [chunk(execution, 1, ["changed"]), chunk(execution, 3, ["gap"])]:
        with pytest.raises(PermissionDeniedError) as error:
            await upload(execution, logs, data)
        assert error.value.status_code == 409
    assert len(indexes.indexes) == 1


async def test_object_storage_failure_never_advances_the_cursor(
    execution: Execution,
    reporting: Reporting,
    fake_stores: FakeStores,
    mocker: MockerFixture,
) -> None:
    logs, indexes, run = reporting
    put = mocker.patch.object(fake_stores.blob, "put", side_effect=OSError("offline"))
    with pytest.raises(OSError, match="offline"):
        await upload(execution, logs, chunk(execution, 1, ["first"]))
    assert not indexes.indexes
    context = await indexes.context(run.repo_id, run.id, next(iter(execution[1].attempts)))
    assert context is not None
    assert context.log_seq == 0
    put.side_effect = None


async def test_redis_loss_and_tail_failure_replay_from_durable_storage(
    execution: Execution,
    reporting: Reporting,
    fake_stores: FakeStores,
    mocker: MockerFixture,
) -> None:
    logs, _, run = reporting
    mocker.patch.object(fake_stores.redis, "stream_add", side_effect=OSError("offline"))
    data = chunk(execution, 1, ["first", "second", "third"])
    assert await upload(execution, logs, data) == 3
    fake_stores.redis.streams.clear()
    page = await logs.page(run.repo_id, run.id, data.id, 1)
    assert [item.seq for item in page.records] == [2, 3]
    mocker.patch.object(fake_stores.redis, "stream_read", side_effect=OSError("offline"))
    assert (await logs.page(run.repo_id, run.id, data.id, 2)).records[0].msg == "third"


async def test_completion_waits_for_logs_and_replay_stops_at_the_last_sequence(
    execution: Execution,
    reporting: Reporting,
    fake_stores: FakeStores,
) -> None:
    logs, _, run = reporting
    service, _, sandbox, _ = execution
    attempt_id, authorization, raw = completion(sandbox)
    result = json.loads(raw)
    result["last_seq"] = 2
    with pytest.raises(ActionsUnavailableError):
        await service.complete(attempt_id, authorization, json.dumps(result).encode())
    assert run.jobs[0]["status"] == "running"
    await upload(execution, logs, chunk(execution, 1, ["one", "two"]))
    await service.complete(attempt_id, authorization, json.dumps(result).encode())
    fake_stores.redis.streams.clear()
    events = "".join([event async for event in logs.stream(run.repo_id, run.id, attempt_id, 1)])
    assert "id: 2\nevent: log" in events
    assert "id: 1\nevent: log" not in events
    assert 'event: end\ndata: {"last_seq":2}' in events
    assert "".join([text async for text in logs.download(run.repo_id, run.id, attempt_id)]) == "one\ntwo\n"


@pytest.mark.parametrize("field", ["id", "job_id", "generation", "fence"])
async def test_fenced_report_cannot_change_another_attempt(
    execution: Execution, reporting: Reporting, field: str
) -> None:
    logs, indexes, _ = reporting
    data = chunk(execution, 1, ["stale"])
    other = data.model_copy(
        update={field: 2 if field == "generation" else "wrong" if field == "job_id" else uuid.uuid4()}
    )
    with pytest.raises(PermissionDeniedError):
        await upload(execution, logs, other)
    assert not indexes.indexes


async def test_cancellation_revokes_writes_but_preserves_history(execution: Execution, reporting: Reporting) -> None:
    logs, _, run = reporting
    data = chunk(execution, 1, ["before cancellation"])
    await upload(execution, logs, data)
    await execution[0].dispatcher.cancel(run.repo_id, run.id)
    with pytest.raises(PermissionDeniedError):
        await upload(execution, logs, chunk(execution, 2, ["late"]))
    page = await logs.page(run.repo_id, run.id, data.id, 0)
    assert page.complete
    assert page.records[0].msg == "before cancellation"


async def test_large_history_is_paginated_without_growing_the_run_json(
    execution: Execution, reporting: Reporting
) -> None:
    logs, _, run = reporting
    row_size = len(json.dumps(run.jobs))
    count = 0
    for _ in range(12):
        await upload(execution, logs, chunk(execution, count + 1, ["x" * 4096] * 12))
        count += 12
    cursor = 0
    seen = []
    while cursor < count:
        page = await logs.page(run.repo_id, run.id, next(iter(execution[1].attempts)), cursor)
        assert len(page.model_dump_json().encode()) < 300 * 1024
        assert page.next_seq > cursor
        seen.extend(item.seq for item in page.records)
        cursor = page.next_seq
    assert seen == list(range(1, count + 1))
    assert len(json.dumps(run.jobs)) == row_size
