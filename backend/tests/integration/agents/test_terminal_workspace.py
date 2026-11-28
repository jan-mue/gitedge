from typing import TYPE_CHECKING

import restate
from pydantic_ai import RunContext
from pydantic_ai.toolsets import FunctionToolset
from pydantic_ai.usage import RunUsage
from restate.ext.pydantic._toolset import RestateContextRunToolSet
from restate.ext.pydantic._utils import current_state, state_context
from restate.ext.turnstile import Turnstile

from app.agents.main import stop_workspace
from app.agents.restate import RestateWorkspaceErrors
from tests.integration.agents.containers import RESTATE_IMAGE

if TYPE_CHECKING:
    from pydantic_ai.models.ollama import OllamaModel
    from pydantic_ai_harness.smol_sandbox import SmolSandboxBackend


async def test_dead_vm_fails_without_retrying_the_tool(
    smol_sandbox: SmolSandboxBackend, agent_model: OllamaModel
) -> None:
    await stop_workspace(smol_sandbox)
    attempts = 0
    functions = FunctionToolset[None]()

    @functions.tool_plain
    async def read_dead_vm() -> str:
        nonlocal attempts
        attempts += 1
        result = await smol_sandbox.run(["cat", "/workspace/missing.txt"])
        return result.stdout

    toolset = RestateWorkspaceErrors[None]().get_wrapper_toolset(
        RestateContextRunToolSet(functions, restate.RunOptions(max_attempts=3))
    )
    service = restate.Service("TerminalWorkspaceTest")

    @service.handler()
    async def run(_ctx: restate.Context, _prompt: str) -> str:
        ctx = RunContext(deps=None, model=agent_model, usage=RunUsage(), tool_call_id="dead-vm")
        tool = (await toolset.get_tools(ctx))["read_dead_vm"]
        with state_context():
            current_state().turnstile = Turnstile(["dead-vm"])
            try:
                await toolset.call_tool("read_dead_vm", {}, ctx, tool)
            except restate.TerminalError as error:
                return error.message
        return "unexpected success"

    async with restate.create_test_harness(
        restate.app([service], protocol="request_response"), restate_image=RESTATE_IMAGE, always_replay=True
    ) as harness:
        assert await harness.client.service_call(run, arg="Read the deleted VM") == "WorkspaceError"
    assert attempts == 1
