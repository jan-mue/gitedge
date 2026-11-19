import json
import uuid
from typing import TYPE_CHECKING

import pytest
import restate
from pydantic_ai.models.test import TestModel
from pydantic_ai.workspaces import WorkspaceBackend, WorkspaceError, WorkspaceRef
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.dependencies import CODING_AGENT_DEPS, CodingAgentDeps
from app.agents.runtime import run, run_agent_turn
from app.clients.agent_streams import AgentStreamStore
from app.clients.agents import AgentStore
from app.entities.agents import AgentRun, AgentSession

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from pytest_mock import MockerFixture

    from app.schemas.agent_turns import AgentTurnRequest


@pytest.mark.parametrize("cleanup_failure", ["snapshot", "stop"])
async def test_permanent_error_records_terminal_status_despite_failed_cleanup(
    mocker: MockerFixture, cleanup_failure: str
) -> None:
    session = AgentSession(id=uuid.uuid4(), user_id=uuid.uuid4(), environment_id=uuid.uuid4(), kind="coding")
    turn = AgentRun(id=uuid.uuid4(), session_id=session.id, model="local:model", status="pending")
    db = mocker.create_autospec(AsyncSession, instance=True)
    store = AgentStore(db)
    mocker.patch.object(store, "run", return_value=turn)
    mocker.patch.object(store, "get", return_value=session)
    mocker.patch("app.agents.runtime.AgentStore", return_value=store)
    engine = mocker.MagicMock()
    mocker.patch("app.agents.runtime.create_db_engine", return_value=engine)
    database_context = mocker.MagicMock()
    database_context.__aenter__.return_value = db
    mocker.patch("app.agents.runtime.create_session_factory", return_value=mocker.Mock(return_value=database_context))
    model_context = mocker.MagicMock()
    model_context.__aenter__.return_value = TestModel()
    mocker.patch("app.agents.runtime.account_model", return_value=model_context)
    machine = mocker.create_autospec(WorkspaceBackend, instance=True)
    machine.ref = WorkspaceRef(provider="smol", id="test-vm")
    mocker.patch("app.agents.runtime.workspace_backend", return_value=machine)
    mocker.patch("app.agents.runtime.capture_worktrees", return_value=[])
    mocker.patch("app.agents.runtime.run_coding_agent", side_effect=WorkspaceError("private damaged-output details"))
    snapshot = mocker.patch("app.agents.runtime.snapshot_workspace", return_value="checkpoint")
    stop = mocker.patch("app.agents.runtime.stop_workspace")
    if cleanup_failure == "snapshot":
        snapshot.side_effect = WorkspaceError("snapshot unavailable")
    else:
        stop.side_effect = restate.TerminalError("stop unavailable")
    streams = mocker.create_autospec(AgentStreamStore, instance=True)
    streams.cancelled.return_value = False
    deps = CodingAgentDeps(streams=streams, blobs=mocker.Mock(), sandbox=mocker.Mock())
    ctx = mocker.create_autospec(restate.ObjectContext, instance=True)
    ctx.key.return_value = str(session.id)

    async def execute(name: str, action: Callable[[], Awaitable[object]], _options: restate.RunOptions) -> object:
        if name == "load authorized turn":
            return {
                "status": "pending",
                "prompt": "work",
                "model": "local:model",
                "user_id": str(session.user_id),
                "snapshot": None,
                "setup": False,
                "instructions": "",
                "history": [],
                "repositories": [],
            }
        return await action()

    ctx.run_typed.side_effect = execute

    async def invoke(_handler: object, *, arg: AgentTurnRequest) -> object:
        return await run_agent_turn(ctx, arg)

    ctx.service_call.side_effect = invoke
    token = CODING_AGENT_DEPS.set(deps)
    try:
        assert await run(ctx, str(turn.id)) == str(turn.id)
    finally:
        CODING_AGENT_DEPS.reset(token)
    assert turn.status == "failed"
    assert turn.error == "WorkspaceError"
    assert turn.finished_at is not None
    terminal = json.loads(streams.append.call_args.args[2])
    assert terminal["type"] == "RUN_ERROR"
    assert terminal["code"] == "WorkspaceError"
    assert "private" not in terminal["message"]
    stop.assert_awaited_once()
