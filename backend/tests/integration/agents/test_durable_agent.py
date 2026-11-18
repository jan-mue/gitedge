import json
from typing import TYPE_CHECKING

import restate

from app.agents.coding import run_coding_agent
from tests.integration.agents.harness import agent_harness

if TYPE_CHECKING:
    from pydantic_ai.models.openai import OpenAIChatModel

    from app.agents.dependencies import CodingAgentDeps


async def test_restate_agent_tokens(agent_coding_deps: CodingAgentDeps, agent_model: OpenAIChatModel) -> None:
    service = restate.Service("TestCodingAgent")

    @service.handler()
    async def run(_ctx: restate.Context, prompt: str) -> str:
        messages = await run_coding_agent(
            agent_coding_deps,
            run_id="turn-1",
            session_id="session-1",
            prompt=prompt,
            model=agent_model,
        )
        return str(len(messages))

    async with agent_harness(restate.app([service], protocol="request_response"), disable_retries=True) as harness:
        result = await harness.client.service_call(run, arg="Reply with hello. Do not use any tools.")
    assert int(result) >= 2
    types = [json.loads(value)["type"] for value in await agent_coding_deps.streams.history("turn-1")]
    assert types[0] == "RUN_STARTED"
    assert types[-1] == "RUN_FINISHED"
    assert "TEXT_MESSAGE_CONTENT" in types
