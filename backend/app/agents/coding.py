"""PydanticAI coding harness running in the backend, with sandbox-only tools."""

import json
from typing import TYPE_CHECKING, override
from uuid import NAMESPACE_URL, uuid5

from ag_ui.core import BaseEvent, CustomEvent
from pydantic import TypeAdapter
from pydantic_ai import Agent, AgentRunResultEvent, RunContext
from pydantic_ai.messages import AgentStreamEvent
from pydantic_ai.ui.ag_ui import AGUIAdapter, AGUIEventStream
from pydantic_ai.usage import UsageLimits
from pydantic_ai_harness.coder import Coder
from restate.ext.pydantic import RestateAgent

from app.agents.providers import resolve_model
from app.agents.workspace import AgentWorkspace, SandboxWorkspace

if TYPE_CHECKING:
    from collections.abc import AsyncIterable

    from pydantic_ai.models import Model

    from app.clients.agent_streams import AgentEventStore
    from app.clients.sandbox import SnapshotableSandboxClient


class StableAGUIEventStream(AGUIEventStream):
    """Use deterministic message IDs when rebuilding a transformer after a crash."""

    message_sequence: int = 0

    @override
    def new_message_id(self) -> str:
        self.message_sequence += 1
        self.message_id = str(uuid5(NAMESPACE_URL, f"{self.run_id}:message:{self.message_sequence}"))
        return self.message_id


async def run_coding_agent(
    sandbox: SnapshotableSandboxClient,
    streams: AgentEventStore,
    *,
    run_id: str,
    session_id: str,
    prompt: str,
    model: str | Model,
    instructions: str = "",
    history: list | None = None,
    finish_stream: bool = True,
) -> list:
    """Execute a durable turn and persist AG-UI tokens and command output.

    The caller owns start/snapshot/stop. RestateAgent journals model calls and
    harness tool calls; stream events are persisted before delivery to clients.
    """
    event_sequence = 0

    async def publish(event: BaseEvent) -> None:
        nonlocal event_sequence
        event_sequence += 1
        await streams.append(run_id, f"agui:{event_sequence}", event.model_dump_json(by_alias=True, exclude_none=True))

    log_positions: dict[str, int] = {}

    async def output(stream: str, chunk: str) -> None:
        key = f"{workspace.command_id}:{stream}"
        offset = log_positions.get(key, 0)
        log_positions[key] = offset + len(chunk)
        event = CustomEvent(
            name="bash_output", value={"command_id": workspace.command_id, "stream": stream, "chunk": chunk}
        )
        await streams.append(run_id, f"bash:{key}:{offset}", event.model_dump_json(by_alias=True))

    workspace = SandboxWorkspace(sandbox, run_id, output)
    agent = Agent(
        resolve_model(model) if isinstance(model, str) else model,
        capabilities=[AgentWorkspace(backend=workspace), Coder(sub_agents=False)],
        instructions=instructions,
    )
    run_input = AGUIAdapter.build_run_input(
        (
            '{"threadId":"'
            + session_id
            + '","runId":"'
            + run_id
            + '","messages":[],"tools":[],"context":[],"state":{}}'
        ).encode()
    )
    adapter = AGUIAdapter(agent=agent, run_input=run_input)
    transformer = StableAGUIEventStream(run_input=adapter.run_input)
    transformer.message_id = str(uuid5(NAMESPACE_URL, f"{run_id}:message"))

    native_adapter = TypeAdapter(AgentStreamEvent)
    seen: set[str] = set()

    # Restate skips callbacks of journaled model/tool steps on replay. Rebuild
    # transformer state from persisted native events before handling the next step.
    for record in await streams.history(f"{run_id}:native"):
        item = json.loads(record)
        seen.add(item["id"])
        native = native_adapter.validate_json(item["event"])
        async for event in transformer.handle_event(native):
            await publish(event)

    async def events(ctx: RunContext, source: AsyncIterable[AgentStreamEvent]) -> None:
        index = 0
        async for native in source:
            call = getattr(getattr(native, "part", None), "tool_call_id", None)
            identity = f"{ctx.run_step}:{call or 'model'}:{type(native).__name__}:{index}"
            index += 1
            if identity in seen:
                continue
            encoded = native_adapter.dump_json(native).decode()
            await streams.append(f"{run_id}:native", identity, json.dumps({"id": identity, "event": encoded}))
            seen.add(identity)
            async for event in transformer.handle_event(native):
                await publish(event)

    durable = RestateAgent(agent, event_stream_handler=events, auto_wrap_tools=True)
    async for event in transformer.before_stream():
        await streams.append(run_id, "start", event.model_dump_json(by_alias=True))
    result = await durable.run(prompt, message_history=history, usage_limits=UsageLimits(request_limit=100))
    async for event in transformer.handle_event(AgentRunResultEvent(result=result)):
        await publish(event)
    async for event in transformer.after_stream():
        if finish_stream or event.type != "RUN_FINISHED":
            await publish(event)
    return result.all_messages()
