from typing import TYPE_CHECKING

import restate

from app.agents.coding import run_coding_agent
from tests.integration.agents.harness import agent_harness

if TYPE_CHECKING:
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai_harness.smol_sandbox import SmolSandboxBackend

    from app.agents.dependencies import CodingAgentDeps
    from app.clients.agent_streams import AgentStreamStore


async def test_ollama_durable_turn(
    agent_sandbox: SmolSandboxBackend,
    agent_streams: AgentStreamStore,
    agent_model: OpenAIChatModel,
    agent_coding_deps: CodingAgentDeps,
) -> None:
    service = restate.Service("OllamaCodingTest")

    @service.handler()
    async def run(_ctx: restate.Context, prompt: str) -> str:
        await run_coding_agent(
            agent_coding_deps,
            run_id="ollama-turn",
            session_id="ollama-session",
            prompt=prompt,
            model=agent_model,
        )
        return "done"

    async with agent_harness(restate.app([service], protocol="request_response"), disable_retries=True) as harness:
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
