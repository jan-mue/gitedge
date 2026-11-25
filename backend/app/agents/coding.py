"""A coding agent with required sandbox resources and authorized forge tools."""

from typing import TYPE_CHECKING

from pydantic_ai import Agent
from pydantic_ai_harness.coder import Coder

from app.agents.dependencies import CodingAgentDeps
from app.agents.forge import GitEdgeForge
from app.agents.providers import resolve_model
from app.agents.restate import RestateToolOrdering, RestateWorkspaceErrors
from app.agents.runner import run_agent

if TYPE_CHECKING:
    from pydantic_ai.messages import ModelMessage
    from pydantic_ai.models import Model
    from pydantic_ai.workspaces import WorkspaceBackend


def create_coding_agent(
    deps: CodingAgentDeps, model: str | Model, instructions: str = ""
) -> Agent[CodingAgentDeps, str]:
    """Build only the coding agent's capabilities, with no setup/chat dependency branches."""
    return Agent(
        resolve_model(model) if isinstance(model, str) else model,
        deps_type=CodingAgentDeps,
        capabilities=[
            deps.sandbox,
            Coder(sub_agents=False),
            GitEdgeForge(),
            RestateToolOrdering(),
            RestateWorkspaceErrors(),
        ],
        instructions=instructions,
    )


async def run_coding_agent(
    deps: CodingAgentDeps,
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
    """Run the separately typed coding agent with explicit dependencies and native workspace."""
    return await run_agent(
        create_coding_agent(deps, model, instructions),
        deps,
        workspace=workspace,
        run_id=run_id,
        session_id=session_id,
        prompt=prompt,
        history=history,
        finish_stream=finish_stream,
    )
