"""Compatibility hooks for the Restate PydanticAI bridge."""

from typing import TYPE_CHECKING, Any, override

from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.exceptions import ToolFailed
from pydantic_ai.tools import AgentDepsT
from pydantic_ai.toolsets.wrapper import WrapperToolset
from pydantic_ai.workspaces import (
    WorkspaceError,
    WorkspaceOutputLimitError,
    WorkspaceReadOnlyError,
    WorkspaceTimeoutError,
)
from restate import TerminalError
from restate.ext.pydantic._toolset import RestateContextRunToolSet
from restate.ext.pydantic._utils import current_state
from restate.ext.turnstile import Turnstile

if TYPE_CHECKING:
    from pydantic_ai.messages import ModelResponse
    from pydantic_ai.models import ModelRequestContext
    from pydantic_ai.tools import RunContext
    from pydantic_ai.toolsets.abstract import AbstractToolset, ToolsetTool


class TerminalWorkspaceTools[DepsT](WrapperToolset[DepsT]):
    """Classify permanent workspace failures inside the SDK's journaled tool call.

    Tool arguments/results are arbitrary JSON or tool-specific Python values,
    matching the upstream toolset interface. Timeouts, output limits and read-only
    refusals keep their existing semantics; provider transport errors propagate.
    """

    @override
    async def call_tool(
        self, name: str, tool_args: dict[str, Any], ctx: RunContext[DepsT], tool: ToolsetTool[DepsT]
    ) -> Any:
        try:
            return await self.wrapped.call_tool(name, tool_args, ctx, tool)
        except (WorkspaceError, ToolFailed) as error:
            cause = error if isinstance(error, WorkspaceError) else error.__cause__
            if isinstance(cause, WorkspaceError) and not isinstance(
                cause, WorkspaceTimeoutError | WorkspaceOutputLimitError | WorkspaceReadOnlyError
            ):
                raise TerminalError("WorkspaceError") from error
            raise


class RestateWorkspaceErrors[DepsT](AbstractCapability[DepsT]):
    """Place permanent-error classification inside, not outside, durable retries."""

    @override
    def get_wrapper_toolset(self, toolset: AbstractToolset[DepsT]) -> AbstractToolset[DepsT]:
        def wrap(current: AbstractToolset[DepsT]) -> AbstractToolset[DepsT]:
            if isinstance(current, RestateContextRunToolSet):
                return RestateContextRunToolSet(TerminalWorkspaceTools(current.wrapped), current.options)
            return current

        return toolset.visit_and_replace(wrap)


class RestateToolOrdering(AbstractCapability[AgentDepsT]):
    """Restore streamed-tool ordering omitted by restate-sdk 1.5.2-1.5.4.

    The hook runs outside the journaled model call, so it also reconstructs
    ordering when Restate replays a completed response without its callback.
    Keep the SDK's own turnstile rather than replacing its tool execution.
    """

    @override
    async def after_model_request(
        self,
        ctx: RunContext[AgentDepsT],
        *,
        request_context: ModelRequestContext,
        response: ModelResponse,
    ) -> ModelResponse:
        current_state().turnstile = Turnstile([call.tool_call_id for call in response.tool_calls])
        return response
