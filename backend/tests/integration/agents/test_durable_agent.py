import json
from typing import TYPE_CHECKING

import restate

from app.agents.setup import run_setup_agent
from tests.integration.agents.containers import RESTATE_IMAGE

if TYPE_CHECKING:
    from app.clients.agent_streams import AgentStreamStore
    from tests.integration.agents.conftest import AgentRunResources


async def test_restate_agent_tokens(agent_run_resources: AgentRunResources, agent_streams: AgentStreamStore) -> None:
    service = restate.Service("TestCodingAgent")

    @service.handler()
    async def run(_ctx: restate.Context, prompt: str) -> str:
        async with agent_run_resources(None) as (deps, workspace, model):
            messages = await run_setup_agent(
                deps, workspace=workspace, run_id="turn-1", session_id="session-1", prompt=prompt, model=model
            )
            return str(len(messages))

    async with restate.create_test_harness(
        restate.app([service], protocol="request_response"),
        restate_image=RESTATE_IMAGE,
        always_replay=True,
        disable_retries=True,
    ) as harness:
        result = await harness.client.service_call(run, arg="Reply with hello. Do not use any tools.")
    assert int(result) >= 2
    types = [json.loads(value)["type"] for value in await agent_streams.history("turn-1")]
    assert types[0] == "RUN_STARTED"
    assert types[-1] == "RUN_FINISHED"
    assert "TEXT_MESSAGE_CONTENT" in types
