from typing import TYPE_CHECKING

import pytest
import restate
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic_ai import RunContext
from pydantic_ai.exceptions import ToolFailed
from pydantic_ai.models.test import TestModel
from pydantic_ai.toolsets import FunctionToolset
from pydantic_ai.usage import RunUsage
from pydantic_ai.workspaces import (
    WorkspaceError,
    WorkspaceOutputLimitError,
    WorkspaceReadOnlyError,
    WorkspaceTimeoutError,
)
from restate.ext.pydantic._toolset import RestateContextRunToolSet
from restate.ext.pydantic._utils import current_state, state_context
from restate.ext.turnstile import Turnstile

from app.agents.restate import RestateWorkspaceErrors, TerminalWorkspaceTools
from app.agents.runtime import agent_sessions

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from pytest_mock import MockerFixture


@pytest.mark.parametrize("wrapped_failure", [False, True])
async def test_permanent_workspace_failure_is_terminal_inside_journal(
    mocker: MockerFixture, wrapped_failure: bool
) -> None:
    calls = 0
    functions = FunctionToolset[None]()

    @functions.tool_plain
    async def broken() -> str:
        nonlocal calls
        calls += 1
        try:
            raise WorkspaceError("damaged filesystem output containing private paths")
        except WorkspaceError as error:
            if wrapped_failure:
                raise ToolFailed(str(error)) from error
            raise

    ctx = RunContext(deps=None, model=TestModel(), usage=RunUsage(), tool_call_id="broken-call")
    context = mocker.create_autospec(restate.Context, instance=True)

    async def execute(_name: str, action: Callable[[], Awaitable[object]], _options: restate.RunOptions) -> object:
        return await action()

    context.run_typed.side_effect = execute
    mocker.patch("restate.ext.pydantic._toolset.current_context", return_value=context)
    durable = RestateContextRunToolSet(functions, restate.RunOptions(max_attempts=3))
    toolset = RestateWorkspaceErrors[None]().get_wrapper_toolset(durable)
    tool = (await toolset.get_tools(ctx))["broken"]
    with state_context():
        current_state().turnstile = Turnstile(["broken-call"])
        with pytest.raises(restate.TerminalError, match=r"^WorkspaceError$"):
            await toolset.call_tool("broken", {}, ctx, tool)
    assert calls == 1
    context.run_typed.assert_called_once()


@pytest.mark.parametrize(
    "error",
    [
        ConnectionError("temporary transport failure"),
        ToolFailed("missing resource the model can handle"),
        WorkspaceTimeoutError("command timed out"),
        WorkspaceReadOnlyError("read-only refusal"),
        WorkspaceOutputLimitError("large output", limit=10),
    ],
)
async def test_other_tool_errors_keep_their_semantics(error: Exception) -> None:
    functions = FunctionToolset[None]()

    @functions.tool_plain
    async def broken() -> str:
        raise error

    ctx = RunContext(deps=None, model=TestModel(), usage=RunUsage())
    toolset = TerminalWorkspaceTools(functions)
    tool = (await toolset.get_tools(ctx))["broken"]
    with pytest.raises(type(error)) as caught:
        await toolset.call_tool("broken", {}, ctx, tool)
    assert caught.value is error


def test_discovery_advertises_bounded_invocation_retries() -> None:
    app = FastAPI()
    app.mount("/restate", restate.app(services=[agent_sessions], protocol="request_response"))
    with TestClient(app) as client:
        response = client.get(
            "/restate/discover", headers={"Accept": "application/vnd.restate.endpointmanifest.v4+json"}
        )
    assert response.status_code == 200
    service = response.json()["services"][0]
    assert service["retryPolicyMaxAttempts"] == 3
    assert service["retryPolicyOnMaxAttempts"] == "PAUSE"
