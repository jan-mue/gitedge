import json
from typing import TYPE_CHECKING

import restate
from pydantic_ai.models.test import TestModel

from app.agents.coding import run_coding_agent
from tests.integration.agents.containers import RESTATE_IMAGE
from tests.integration.agents.fakes import FilesystemTestSandbox, MemoryAgentStreams

if TYPE_CHECKING:
    from pathlib import Path


async def test_restate_agent_tokens(tmp_path: Path) -> None:
    sandbox = FilesystemTestSandbox(tmp_path)
    streams = MemoryAgentStreams()
    service = restate.Service("TestCodingAgent")

    @service.handler()
    async def run(_ctx: restate.Context, prompt: str) -> str:
        messages = await run_coding_agent(
            sandbox,
            streams,
            run_id="turn-1",
            session_id="session-1",
            prompt=prompt,
            model=TestModel(custom_output_text="Hello", call_tools=[]),
        )
        return str(len(messages))

    async with restate.create_test_harness(
        restate.app([service]), always_replay=True, restate_image=RESTATE_IMAGE, disable_retries=True
    ) as harness:
        result = await harness.client.service_call(run, arg="Say hello")
    assert int(result) >= 2
    types = [json.loads(value)["type"] for (key, _event_id), value in streams.records.items() if key == "turn-1"]
    assert types[0] == "RUN_STARTED"
    assert types[-1] == "RUN_FINISHED"
    assert "TEXT_MESSAGE_CONTENT" in types
