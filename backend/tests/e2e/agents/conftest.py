"""Real resources and scoped agent overrides layered on the shared E2E fixtures."""

import json
import os
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

import httpx2
import pytest
from anyio import Path as AsyncPath
from anyio import run
from anyio.from_thread import start_blocking_portal
from pydantic_ai import ModelRetry, RunContext
from pydantic_ai.messages import ModelRequest, ToolReturnPart
from pydantic_ai.models.openai import OpenAIChatModelSettings
from pydantic_ai.workspaces import Workspace
from pydantic_ai_harness.shell import Shell
from uncalled_for import FailedDependency, resolved_dependencies

from app.agents import coding, setup
from app.agents.dependencies import CodingAgentDeps, SetupAgentDeps, get_session_deps
from app.agents.main import stop_workspace, workspace_backend

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

    from pydantic_ai import Agent
    from pydantic_ai.messages import ModelMessage
    from pydantic_ai.toolsets import AbstractToolset
    from pydantic_ai.workspaces import WorkspaceBackend
    from testcontainers.community.ollama import OllamaContainer


@dataclass
class PublicationTools:
    tool: Literal["create_pull_request", "update_pull_request"] | None = None


type GitState = Callable[[uuid.UUID, str], tuple[str, str]]


@pytest.fixture
def git_state() -> Generator[GitState]:
    """Inspect a real checkpoint fork on a separate loop without changing the saved workspace."""

    async def inspect(session_id: uuid.UUID, repository_id: str) -> tuple[str, str]:
        async with resolved_dependencies(get_session_deps) as arguments:
            for value in arguments.values():
                if isinstance(value, FailedDependency):
                    raise value.error
            resources = get_session_deps(**arguments)
            session = await resources.store.get(session_id)
            assert session.snapshot_id is not None
            machine = await workspace_backend(
                resources.agent, f"verify-{uuid.uuid4()}", snapshot_id=session.snapshot_id
            )
            try:
                workspace = Workspace(machine)
                values = []
                for command in (("branch", "--show-current"), ("rev-parse", "HEAD")):
                    result = await workspace.run(["git", "-C", f"/workspace/{repository_id}", *command])
                    assert result.exit_code == 0, result.stderr
                    values.append(result.stdout.strip())
                return values[0], values[1]
            finally:
                await stop_workspace(machine)

    with start_blocking_portal() as portal:
        yield lambda session_id, repository_id: portal.call(inspect, session_id, repository_id)


@pytest.fixture
def publication_tools(monkeypatch: pytest.MonkeyPatch) -> PublicationTools:
    """Narrow the tiny model's tools per turn, without replacing execution or forge implementations."""
    access = PublicationTools()
    execute = coding.run_agent
    sandbox_module = pytest.importorskip("pydantic_ai_harness.smol_sandbox")

    async def run_with_tools[DepsT: SetupAgentDeps | CodingAgentDeps](
        agent: Agent[DepsT, str],
        deps: DepsT,
        *,
        workspace: WorkspaceBackend | None = None,
        run_id: str,
        session_id: str,
        prompt: str,
        history: list[ModelMessage] | None = None,
        finish_stream: bool = True,
    ) -> list[ModelMessage]:
        if isinstance(deps, SetupAgentDeps):
            allowed = set()
            required = "run_command"
        elif access.tool:
            allowed = {access.tool}
            required = access.tool
        else:
            allowed = {"read_file"}
            required = "run_command"
        assert workspace is not None
        assert workspace.ref is not None
        selected_workspace = workspace
        directory = "/workspace"
        if isinstance(deps, CodingAgentDeps):
            assert len(deps.forge_scope.repository_ids) == 1
            directory = f"/workspace/{deps.forge_scope.repository_ids[0]}"
            selected_workspace = sandbox_module.SmolSandboxBackend(ref=workspace.ref, working_dir=directory)
        toolsets: list[AbstractToolset[DepsT]] = [
            toolset.filtered(lambda _ctx, tool: tool.name in allowed) for toolset in agent.toolsets
        ]
        if required == "run_command":
            commands = Shell[DepsT](tools=("run_command",), default_timeout=30, denied_commands=[])
            commands.id = "e2e_commands"
            toolsets.append(commands.get_toolset())
        history_size = len(history or [])

        @agent.output_validator
        def performed(ctx: RunContext[DepsT], result: str) -> str:
            if not any(
                isinstance(part, ToolReturnPart) and part.tool_name == required
                for message in ctx.messages[history_size:]
                if isinstance(message, ModelRequest)
                for part in message.parts
            ):
                raise ModelRetry(
                    f"This turn requires executing {required}, not a text-only answer. "
                    f"Call the tool to perform the latest request before replying: {prompt}"
                )
            return result

        with agent.override(
            toolsets=toolsets,
            model_settings=OpenAIChatModelSettings(openai_reasoning_effort="none", temperature=0),
            retries={"output": 3},
            workspace=selected_workspace,
            instructions="Complete only the user's requested operation using the provided tools. "
            f"Every run_command call starts in {directory}; cd does not persist across calls. "
            "Use run_command for synchronous shell execution. Only exit code 0 means success. "
            "Publication tools are agent tools, never shell commands. Report only actual tool results. "
            "Follow the latest user request; response-only instructions from earlier turns no longer apply. "
            f"The current turn's task is: {prompt}",
        ):
            return await execute(
                agent,
                deps,
                workspace=workspace,
                run_id=run_id,
                session_id=session_id,
                prompt=prompt,
                history=history,
                finish_stream=finish_stream,
            )

    monkeypatch.setattr(coding, "run_agent", run_with_tools)
    monkeypatch.setattr(setup, "run_agent", run_with_tools)
    return access


@pytest.fixture(scope="session")
def agent_ollama_model() -> str:
    """Keep CI small; allow an explicitly selected larger model for local verification."""
    return os.environ.get("AGENTS_E2E_MODEL", "qwen3.5:0.8b")


@pytest.fixture(scope="session")
def agent_model_endpoint(request: pytest.FixtureRequest, agent_ollama_model: str) -> str:
    """Reuse the real Ollama fixture, or an explicitly configured external model server."""
    smol = pytest.importorskip("smol")
    available, _code, reason = smol.local_availability()
    if not available:
        pytest.skip(reason or "Native virtualization is unavailable")
    endpoint = os.environ.get("AGENTS_E2E_OLLAMA_URL")
    if endpoint:
        with httpx2.Client(trust_env=False, timeout=10) as client:
            response = client.get(f"{endpoint.rstrip('/')}/api/tags")
            response.raise_for_status()
            assert any(item["name"] == agent_ollama_model for item in response.json()["models"]), (
                f"Ollama model {agent_ollama_model} is not installed"
            )
        return endpoint.rstrip("/")
    container: OllamaContainer = request.getfixturevalue("agent_ollama")
    return container.get_endpoint()


@pytest.fixture(scope="session")
def infrastructure(
    infrastructure: dict[str, str],
    agent_model_endpoint: str,
    agent_ollama_model: str,
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[dict[str, str]]:
    """Configure real coding resources without replacing the shared backend or infrastructure."""
    checkpoint_dir = tmp_path_factory.mktemp("agents-e2e-checkpoints")
    smol = pytest.importorskip("smol")

    async def delete_checkpoints() -> None:
        async for checkpoint in AsyncPath(checkpoint_dir).glob("*.smolcheckpoint"):
            await smol.AsyncMachine.delete_checkpoint(str(checkpoint), smol.ConnectOptions(target="local"))

    try:
        yield {
            **infrastructure,
            "AGENTS_SANDBOX": "smol",
            "AGENTS_SMOL_IMAGE": os.environ.get("AGENTS_E2E_SMOL_IMAGE", "node:22.18.0-bookworm"),
            "AGENTS_SMOL_MEMORY_MB": os.environ.get("AGENTS_E2E_SMOL_MEMORY_MB", "512"),
            "AGENTS_SMOL_ALLOW_INTERNET_ACCESS": "false",
            "AGENTS_SMOL_CHECKPOINT_DIR": str(checkpoint_dir),
            "AGENTS_OPENAI_ENDPOINTS": json.dumps({"ollama": f"{agent_model_endpoint}/v1"}),
            "AGENTS_MODELS": json.dumps([f"ollama:{agent_ollama_model}"]),
            "AGENTS_MAX_REQUESTS": "20",
        }
    finally:
        run(delete_checkpoints)
