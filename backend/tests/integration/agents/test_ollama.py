from typing import TYPE_CHECKING

import restate

from app.agents.setup import run_setup_agent
from tests.integration.agents.containers import RESTATE_IMAGE

if TYPE_CHECKING:
    from pydantic_ai.workspaces import SupportsCommands

    from app.clients.agent_streams import AgentStreamStore
    from tests.integration.agents.conftest import AgentRunResources


async def test_ollama_durable_turn(
    agent_sandbox: SupportsCommands,
    agent_streams: AgentStreamStore,
    agent_run_resources: AgentRunResources,
) -> None:
    service = restate.Service("OllamaCodingTest")

    @service.handler()
    async def run(_ctx: restate.Context, prompt: str) -> str:
        async with agent_run_resources(None) as (deps, workspace, model):
            await run_setup_agent(
                deps, workspace=workspace, run_id="ollama-turn", session_id="ollama-session", prompt=prompt, model=model
            )
            return "done"

    async with restate.create_test_harness(
        restate.app([service], protocol="request_response"),
        restate_image=RESTATE_IMAGE,
        always_replay=True,
        disable_retries=True,
    ) as harness:
        assert (
            await harness.client.service_call(
                run,
                arg='Call the shell tool with command "echo hello > /workspace/hello.txt; cat /workspace/hello.txt". Execute it now; do not just describe the command. Then reply briefly.',
            )
        ) == "done"
    events = await agent_streams.history("ollama-turn")
    result = await agent_sandbox.run(["cat", "/workspace/hello.txt"])
    assert result.exit_code == 0, (result.stderr, events)
    assert result.stdout == "hello\n", events
    assert any("TEXT_MESSAGE_CONTENT" in event for event in events)
    assert any("bash_output" in event for event in events)
