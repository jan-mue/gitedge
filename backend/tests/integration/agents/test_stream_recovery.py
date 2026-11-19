import json
from typing import TYPE_CHECKING

import restate
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIChatModelSettings
from pydantic_ai.providers.openai import OpenAIProvider

from app.agents.coding import run_coding_agent
from tests.integration.agents.containers import OLLAMA_MODEL
from tests.integration.agents.harness import agent_harness
from tests.integration.agents.proxy import interrupted_ollama

if TYPE_CHECKING:
    from testcontainers.community.ollama import OllamaContainer

    from app.agents.dependencies import CodingAgentDeps
    from app.clients.agent_streams import AgentStreamStore


async def test_interrupted_model_replaces_partial_tokens(
    agent_coding_deps: CodingAgentDeps, agent_streams: AgentStreamStore, agent_ollama: OllamaContainer
) -> None:
    async with interrupted_ollama(agent_ollama.get_endpoint(), agent_streams, "retry-run") as endpoint:
        provider = OpenAIProvider(base_url=endpoint, api_key="ollama")
        try:
            model = OpenAIChatModel(
                OLLAMA_MODEL, provider=provider, settings=OpenAIChatModelSettings(openai_reasoning_effort="none")
            )
            service = restate.Service("StreamRecovery")

            @service.handler()
            async def run(_ctx: restate.Context, prompt: str) -> str:
                messages = await run_coding_agent(
                    agent_coding_deps,
                    run_id="retry-run",
                    session_id="retry-session",
                    prompt=prompt,
                    model=model,
                )
                return str(len(messages))

            async with agent_harness(restate.app([service], protocol="request_response")) as harness:
                result = await harness.client.service_call(
                    run, arg="Write a short greeting of at least ten words. Do not use any tools."
                )
            assert int(result) >= 2
        finally:
            await provider.client.close()
    events = [json.loads(value) for value in await agent_streams.history("retry-run")]
    resets = [index for index, event in enumerate(events) if event["type"] == "MESSAGES_SNAPSHOT"]
    assert len(resets) == 1
    assert any(event["type"] == "TEXT_MESSAGE_CONTENT" for event in events[: resets[0]])
    assert any(event["type"] == "TEXT_MESSAGE_CONTENT" for event in events[resets[0] + 1 :])
    native = [json.loads(value) for value in await agent_streams.history("retry-run:native")]
    assert sum(bool(event.get("reset")) for event in native) == 1
    assert events[-1]["type"] == "RUN_FINISHED"
