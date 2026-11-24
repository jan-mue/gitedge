"""Shared durable PydanticAI execution with replayable AG-UI output."""

import asyncio
import json
from dataclasses import dataclass, field
from functools import partial
from typing import TYPE_CHECKING, override
from uuid import NAMESPACE_URL, uuid5

from ag_ui.core import BaseEvent, CustomEvent, MessagesSnapshotEvent, UserMessage
from pydantic import TypeAdapter
from pydantic_ai import Agent, AgentRunResultEvent, RunContext
from pydantic_ai.messages import AgentStreamEvent
from pydantic_ai.models import StreamedResponse
from pydantic_ai.ui.ag_ui import AGUIAdapter, AGUIEventStream
from pydantic_ai.usage import UsageLimits
from pydantic_ai_harness.shell import CommandOutputEvent
from restate import RunOptions
from restate.ext.pydantic import RestateAgent

from app.agents.cancellation import run_cancellable
from app.agents.dependencies import AgentDeps
from app.config import settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterable, AsyncIterator

    from pydantic_ai.messages import CapabilityEvent, ModelMessage
    from pydantic_ai.workspaces import WorkspaceBackend


@dataclass(kw_only=True)
class StableAGUIEventStream(AGUIEventStream):
    """Deterministic IDs let a transformer reconstruct already delivered events."""

    message_sequence: int = 0
    namespace: str = ""
    command_sequences: dict[str, int] = field(default_factory=dict)

    @override
    def new_message_id(self) -> str:
        self.message_sequence += 1
        self.message_id = str(uuid5(NAMESPACE_URL, f"{self.namespace}:{self.message_sequence}"))
        return self.message_id

    @override
    async def handle_capability_event(self, event: CapabilityEvent) -> AsyncIterator[BaseEvent]:
        """Expose upstream shell output without intercepting workspace execution."""
        if isinstance(event, CommandOutputEvent) and event.tool_call_id is not None:
            command_id = event.tool_call_id
            sequence = self.command_sequences.get(command_id, 0)
            self.command_sequences[command_id] = sequence + 1
            yield CustomEvent(
                name="bash_output",
                value={"command_id": command_id, "stream": "combined", "chunk": event.text, "sequence": sequence},
            )
        else:
            async for output in super().handle_capability_event(event):
                yield output


async def run_agent[AgentDepsT: AgentDeps](
    agent: Agent[AgentDepsT, str],
    deps: AgentDepsT,
    *,
    workspace: WorkspaceBackend | None = None,
    run_id: str,
    session_id: str,
    prompt: str,
    history: list[ModelMessage] | None = None,
    finish_stream: bool = True,
) -> list[ModelMessage]:
    """Journal model/tool results, persist tokens before delivery, and recover interrupted streams.

    A callback is skipped when Restate replays a completed model step. If a model
    callback executes again, its previous request did not commit; a protocol
    snapshot replaces that partial response before the new attempt streams.
    Sandbox-free agents can omit the workspace; setup/coding wrappers require it.
    """
    streams = deps.streams

    async def publish(identity: str, event: BaseEvent) -> None:
        await streams.append(run_id, identity, event.model_dump_json(by_alias=True, exclude_none=True))

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

    async def events(ctx: RunContext[AgentDepsT], source: AsyncIterable[AgentStreamEvent]) -> None:
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
    result = await run_cancellable(
        partial(
            durable.run,
            prompt,
            run_id=run_id,
            message_history=history,
            usage_limits=UsageLimits(request_limit=settings.AGENTS_MAX_REQUESTS),
            # Redis already journals/deduplicates events; the SDK's auto-wrap callback
            # returns an unawaited coroutine in restate-sdk 1.5.2.
            event_stream_handler=events,
            deps=deps,
            workspace=workspace,
        ),
        lambda: streams.cancelled(run_id),
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
