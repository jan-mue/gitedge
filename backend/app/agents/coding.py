"""PydanticAI coding harness with replayable AG-UI output and remote-only tools."""

import asyncio
import json
from typing import TYPE_CHECKING, override
from uuid import NAMESPACE_URL, uuid5

from ag_ui.core import BaseEvent, CustomEvent, MessagesSnapshotEvent, UserMessage
from pydantic import TypeAdapter
from pydantic_ai import Agent, AgentRunResultEvent, RunContext
from pydantic_ai.messages import AgentStreamEvent
from pydantic_ai.models import StreamedResponse
from pydantic_ai.ui.ag_ui import AGUIAdapter, AGUIEventStream
from pydantic_ai.usage import UsageLimits
from pydantic_ai_harness.coder import Coder
from restate import RunOptions
from restate.ext.pydantic import RestateAgent

from app.agents.providers import resolve_model
from app.agents.workspace import AgentWorkspace, SandboxWorkspace
from app.clients.agent_streams import AgentRunCancelledError
from app.config import settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterable

    from pydantic_ai.messages import ModelMessage
    from pydantic_ai.models import Model

    from app.clients.agent_streams import AgentEventStore
    from app.clients.sandbox import SnapshotableSandboxClient


class StableAGUIEventStream(AGUIEventStream):
    """Deterministic IDs let a transformer reconstruct already delivered events."""

    message_sequence: int = 0
    namespace: str = ""

    @override
    def new_message_id(self) -> str:
        self.message_sequence += 1
        self.message_id = str(uuid5(NAMESPACE_URL, f"{self.namespace}:{self.message_sequence}"))
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
    history: list[ModelMessage] | None = None,
    finish_stream: bool = True,
) -> list[ModelMessage]:
    """Journal model/tool results, persist tokens before delivery, and recover interrupted streams.

    A callback is skipped when Restate replays a completed model step. If a model
    callback executes again, its previous request did not commit; a protocol
    snapshot replaces that partial response before the new attempt streams.
    """

    async def publish(identity: str, event: BaseEvent) -> None:
        await streams.append(run_id, identity, event.model_dump_json(by_alias=True, exclude_none=True))

    async def output(stream: str, line: str, command_id: str, sequence: int) -> None:
        event = CustomEvent(
            name="bash_output", value={"command_id": command_id, "stream": stream, "chunk": line, "sequence": sequence}
        )
        await publish(f"bash:{command_id}:{stream}:{sequence}", event)

    workspace = SandboxWorkspace(sandbox, run_id, output, lambda: streams.cancelled(run_id))
    agent = Agent(
        resolve_model(model) if isinstance(model, str) else model,
        capabilities=[AgentWorkspace(backend=workspace), Coder(sub_agents=False)],
        instructions=instructions,
    )
    run_input = AGUIAdapter.build_run_input(
        json.dumps(
            {"threadId": session_id, "runId": run_id, "messages": [], "tools": [], "context": [], "state": {}}
        ).encode()
    )
    adapter = AGUIAdapter(agent=agent, run_input=run_input)

    def transformer_for(namespace: str) -> StableAGUIEventStream:
        transformer = StableAGUIEventStream(run_input=adapter.run_input)
        transformer.namespace = namespace
        transformer.message_id = str(uuid5(NAMESPACE_URL, f"{namespace}:initial"))
        return transformer

    transformer = transformer_for(run_id)
    native_adapter = TypeAdapter(AgentStreamEvent)
    lock = asyncio.Lock()
    seen: set[str] = set()

    async def apply(record: dict) -> None:
        nonlocal transformer
        if record.get("reset"):
            transformer = transformer_for(record["id"])
            messages = AGUIAdapter.dump_messages(history or [])
            messages.append(UserMessage(id=str(uuid5(NAMESPACE_URL, f"{run_id}:user")), content=prompt))
            await publish(record["id"], MessagesSnapshotEvent(messages=messages))
            return
        seen.add(record["id"])
        native = native_adapter.validate_json(record["event"])
        index = 0
        async for event in transformer.handle_event(native):
            await publish(f"{record['id']}:{index}", event)
            index += 1

    async for event in transformer.before_stream():
        await publish("start", event)
    for raw in await streams.history(f"{run_id}:native"):
        await apply(json.loads(raw))

    async def events(ctx: RunContext, source: AsyncIterable[AgentStreamEvent]) -> None:
        step = ctx.run_step
        attempt = 0
        if isinstance(source, StreamedResponse):
            attempt = await streams.attempt(run_id, step)
            if attempt > 1:
                reset = {"id": f"model:{step}:{attempt}:reset", "reset": True}
                async with lock:
                    await streams.append(f"{run_id}:native", reset["id"], json.dumps(reset))
                    await apply(reset)
        index = 0
        async for native in source:
            if await streams.cancelled(run_id):
                raise AgentRunCancelledError("Run stopped")
            call = (
                getattr(getattr(native, "part", None), "tool_call_id", None)
                or getattr(getattr(native, "result", None), "tool_call_id", None)
                or ctx.tool_call_id
                or "model"
            )
            identity = f"{step}:{attempt}:{call}:{type(native).__name__}:{index}"
            index += 1
            record = {"id": identity, "event": native_adapter.dump_json(native).decode()}
            async with lock:
                if identity in seen:
                    continue
                await streams.append(f"{run_id}:native", identity, json.dumps(record))
                await apply(record)

    durable = RestateAgent(
        agent, event_stream_handler=events, auto_wrap_tools=True, run_options=RunOptions(max_attempts=3)
    )
    result = await durable.run(
        prompt, message_history=history, usage_limits=UsageLimits(request_limit=settings.AGENTS_MAX_REQUESTS)
    )
    index = 0
    async for event in transformer.handle_event(AgentRunResultEvent(result=result)):
        await publish(f"result:{index}", event)
        index += 1
    async for event in transformer.after_stream():
        if finish_stream or event.type != "RUN_FINISHED":
            await publish(f"result:{index}", event)
            index += 1
    return result.all_messages()
