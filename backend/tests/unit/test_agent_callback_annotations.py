import inspect
from typing import TYPE_CHECKING

import pytest

from app.agents.runtime import run_agent_turn, snapshot_workspace, stop_workspace
from app.clients.agent_repositories import prepare_environment
from app.clients.agent_traces import capture_traces, capture_worktrees
from app.clients.agents import AgentStore

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable


@pytest.mark.parametrize(
    "callback",
    [
        prepare_environment,
        capture_worktrees,
        capture_traces,
        snapshot_workspace,
        stop_workspace,
        AgentStore.save_snapshot,
        AgentStore.save_run,
        AgentStore.finish,
        AgentStore.fail,
        run_agent_turn,
    ],
)
def test_restate_callback_annotations_resolve_at_runtime(callback: Callable[..., Awaitable[object]]) -> None:
    signature = inspect.signature(callback, eval_str=True)
    assert signature.return_annotation is not inspect.Signature.empty
