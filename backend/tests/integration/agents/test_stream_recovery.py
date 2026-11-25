import json
from typing import TYPE_CHECKING

import restate
from pydantic_ai import Agent

from app.agents.dependencies import AgentDeps
from app.agents.runner import run_agent
from tests.integration.agents.containers import RESTATE_IMAGE
from tests.integration.agents.proxy import interrupted_ollama

if TYPE_CHECKING:
    from testcontainers.community.ollama import OllamaContainer

    from app.clients.agent_streams import AgentStreamStore
    from tests.integration.agents.conftest import AgentModelResources


async def test_interrupted_model_replaces_partial_tokens(
    agent_model_resources: AgentModelResources, agent_streams: AgentStreamStore, agent_ollama: OllamaContainer
) -> None:
    async with interrupted_ollama(agent_ollama.get_endpoint(), agent_streams, "retry-run") as endpoint:
        service = restate.Service(
            "StreamRecovery",
            invocation_retry_policy=restate.InvocationRetryPolicy(max_attempts=3, on_max_attempts="kill"),
        )

        @service.handler()
        async def run(_ctx: restate.Context, prompt: str) -> str:
            async with agent_model_resources(endpoint) as (deps, model):
                messages = await run_agent(
                    Agent(model, deps_type=AgentDeps),
                    deps,
                    run_id="retry-run",
                    session_id="retry-session",
                    prompt=prompt,
                )
                return str(len(messages))

        async with restate.create_test_harness(
            restate.app([service], protocol="request_response"), restate_image=RESTATE_IMAGE, always_replay=True
        ) as harness:
            result = await harness.client.service_call(
                run, arg="Write a short greeting of at least ten words. Do not use any tools."
            )
        assert int(result) >= 2
    events = [json.loads(value) for value in await agent_streams.history("retry-run")]
    resets = [index for index, event in enumerate(events) if event["type"] == "MESSAGES_SNAPSHOT"]
    assert len(resets) == 1
    assert any(event["type"] == "TEXT_MESSAGE_CONTENT" for event in events[: resets[0]])
    assert any(event["type"] == "TEXT_MESSAGE_CONTENT" for event in events[resets[0] + 1 :])
    native = [json.loads(value) for value in await agent_streams.history("retry-run:native")]
    assert sum(bool(event.get("reset")) for event in native) == 1
    assert events[-1]["type"] == "RUN_FINISHED"
