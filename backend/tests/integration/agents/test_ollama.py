from typing import TYPE_CHECKING

import restate
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from app.agents.coding import run_coding_agent
from tests.integration.agents.containers import OLLAMA_MODEL, RESTATE_IMAGE
from tests.integration.agents.fakes import FilesystemTestSandbox, MemoryAgentStreams

if TYPE_CHECKING:
    from pathlib import Path

    from testcontainers.community.ollama import OllamaContainer


async def test_ollama_durable_turn(agent_ollama: OllamaContainer, tmp_path: Path) -> None:
    endpoint = agent_ollama.get_endpoint()
    sandbox = FilesystemTestSandbox(tmp_path)
    streams = MemoryAgentStreams()
    model = OpenAIChatModel(OLLAMA_MODEL, provider=OpenAIProvider(base_url=f"{endpoint}/v1", api_key="ollama"))
    service = restate.Service("OllamaCodingTest")

    @service.handler()
    async def run(_ctx: restate.Context, prompt: str) -> str:
        await run_coding_agent(
            sandbox, streams, run_id="ollama-turn", session_id="ollama-session", prompt=prompt, model=model
        )
        return "done"

    async with restate.create_test_harness(
        restate.app([service]), restate_image=RESTATE_IMAGE, always_replay=True, disable_retries=True
    ) as harness:
        assert await harness.client.service_call(run, arg="Reply with hello. Do not use any tools.") == "done"
    assert any(
        "TEXT_MESSAGE_CONTENT" in event
        for (run_id, _event_id), event in streams.records.items()
        if run_id == "ollama-turn"
    )
