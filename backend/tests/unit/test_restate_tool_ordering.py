from typing import TYPE_CHECKING

import pytest
from pydantic import TypeAdapter
from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models import ModelRequestContext, ModelRequestParameters
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage
from restate.ext.pydantic._utils import current_state, state_context

from app.agents.restate import RestateToolOrdering

if TYPE_CHECKING:
    from collections.abc import AsyncIterable

    from pydantic_ai.messages import AgentStreamEvent


@pytest.mark.parametrize("replayed", [False, True])
@pytest.mark.parametrize("ids", [[], ["first"], ["first", "second", "third"]])
async def test_completed_response_restores_tool_order(ids: list[str], replayed: bool) -> None:
    response = ModelResponse(parts=[ToolCallPart("tool", {}, tool_call_id=call_id) for call_id in ids])
    if replayed:
        adapter = TypeAdapter(ModelResponse)
        response = adapter.validate_json(adapter.dump_json(response))
    model = TestModel()
    ctx = RunContext(deps=None, model=model, usage=RunUsage())
    request = ModelRequestContext(
        model=model, messages=[], model_settings=None, model_request_parameters=ModelRequestParameters()
    )
    capability = RestateToolOrdering[None]()

    with state_context():
        result = await capability.after_model_request(ctx, request_context=request, response=response)
        assert result is response
        turnstile = current_state().turnstile
        assert list(turnstile.events) == ids
        for index, call_id in enumerate(ids):
            assert turnstile.events[call_id].is_set()
            assert all(not turnstile.events[later].is_set() for later in ids[index + 1 :])
            await turnstile.wait_for(call_id)
            turnstile.allow_next_after(call_id)

        await capability.after_model_request(
            ctx, request_context=request, response=ModelResponse(parts=[TextPart("done")])
        )
        assert current_state().turnstile.events == {}


@pytest.mark.parametrize("streaming", [False, True])
async def test_agent_hook_runs_before_tools_and_isolates_runs(streaming: bool) -> None:
    async def events(_ctx: RunContext[None], source: AsyncIterable[AgentStreamEvent]) -> None:
        async for _event in source:
            pass

    agent = Agent(TestModel(), capabilities=[RestateToolOrdering[None]()])
    called: list[str] = []

    @agent.tool
    async def first(ctx: RunContext[None]) -> str:
        assert ctx.tool_call_id is not None
        turnstile = current_state().turnstile
        await turnstile.wait_for(ctx.tool_call_id)
        called.append("first")
        turnstile.allow_next_after(ctx.tool_call_id)
        return "first"

    @agent.tool
    async def second(ctx: RunContext[None]) -> str:
        assert ctx.tool_call_id is not None
        turnstile = current_state().turnstile
        await turnstile.wait_for(ctx.tool_call_id)
        called.append("second")
        turnstile.allow_next_after(ctx.tool_call_id)
        return "second"

    with state_context():
        outer_state = current_state()
        with state_context():
            await agent.run("Use both tools", event_stream_handler=events if streaming else None)
            assert called == ["first", "second"]
            assert current_state() is not outer_state
            assert current_state().turnstile.events == {}
        assert current_state() is outer_state
        assert outer_state.turnstile.events == {}
