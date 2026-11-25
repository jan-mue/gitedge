"""A setup agent that prepares environments without access to forge publication tools."""

from typing import TYPE_CHECKING

from pydantic_ai import Agent
from pydantic_ai_harness.coder import Coder

from app.agents.dependencies import SetupAgentDeps
from app.agents.providers import resolve_model
from app.agents.restate import RestateToolOrdering, RestateWorkspaceErrors
from app.agents.runner import run_agent

if TYPE_CHECKING:
    from pydantic_ai.messages import ModelMessage
    from pydantic_ai.models import Model
    from pydantic_ai.workspaces import WorkspaceBackend


def create_setup_agent(deps: SetupAgentDeps, model: str | Model, instructions: str = "") -> Agent[SetupAgentDeps, str]:
    """Build only setup capabilities; this agent never has forge credentials or tools."""
    return Agent(
        resolve_model(model) if isinstance(model, str) else model,
        deps_type=SetupAgentDeps,
        capabilities=[deps.sandbox, Coder(sub_agents=False), RestateToolOrdering(), RestateWorkspaceErrors()],
        instructions=instructions,
    )


async def run_setup_agent(
    deps: SetupAgentDeps,
    *,
    workspace: WorkspaceBackend,
    run_id: str,
    session_id: str,
    prompt: str,
    model: str | Model,
    instructions: str = "",
    history: list[ModelMessage] | None = None,
    finish_stream: bool = True,
) -> list[ModelMessage]:
    """Run the separately typed setup agent with explicit dependencies and native workspace."""
    return await run_agent(
        create_setup_agent(deps, model, instructions),
        deps,
        workspace=workspace,
        run_id=run_id,
        session_id=session_id,
        prompt=prompt,
        history=history,
        finish_stream=finish_stream,
    )
