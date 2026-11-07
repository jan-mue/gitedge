import asyncio
import json
from typing import TYPE_CHECKING

import restate
from pydantic_ai.models.function import FunctionModel

from app.agents.coding import run_coding_agent
from tests.integration.agents.containers import RESTATE_IMAGE
from tests.integration.agents.fakes import FilesystemTestSandbox, MemoryAgentStreams

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path

    from pydantic_ai.messages import ModelMessage
    from pydantic_ai.models.function import AgentInfo


async def test_interrupted_model_replaces_partial_tokens(tmp_path: Path) -> None:
    attempts = 0
    streams = MemoryAgentStreams()
    sandbox = FilesystemTestSandbox(tmp_path)

    async def response(_messages: list[ModelMessage], _info: AgentInfo) -> AsyncIterator[str]:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            yield "partial response"
            await asyncio.sleep(0.02)
            raise OSError("Simulated interrupted model connection")
        yield "Recovered response"

    model = FunctionModel(stream_function=response)
    service = restate.Service("StreamRecovery")

    @service.handler()
    async def run(_ctx: restate.Context, prompt: str) -> str:
        messages = await run_coding_agent(
            sandbox, streams, run_id="retry-run", session_id="retry-session", prompt=prompt, model=model
        )
        return str(len(messages))

    async with restate.create_test_harness(
        restate.app([service], protocol="request_response"), restate_image=RESTATE_IMAGE, always_replay=True
    ) as harness:
        await harness.client.service_call(run, arg="Say hello")
    events = [json.loads(value) for (run_id, _event_id), value in streams.records.items() if run_id == "retry-run"]
    assert attempts == 2
    assert any(event["type"] == "MESSAGES_SNAPSHOT" for event in events)
    assert any(event["type"] == "TEXT_MESSAGE_CONTENT" and "Recovered" in event["delta"] for event in events)
    assert events[-1]["type"] == "RUN_FINISHED"
