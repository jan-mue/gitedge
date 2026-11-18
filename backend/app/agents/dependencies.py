"""Typed PydanticAI dependencies, composed by the FastAPI request graph."""

from contextvars import ContextVar
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pydantic_ai.capabilities import AbstractCapability
    from pydantic_ai.workspaces import WorkspaceBackend

    from app.clients.agent_streams import AgentEventStore
    from app.clients.blob_storage import BlobStorageClient


@dataclass(kw_only=True)
class CodingAgentDeps:
    """Run resources supplied through FastAPI and PydanticAI dependency injection."""

    streams: AgentEventStore
    blobs: BlobStorageClient
    sandbox: AbstractCapability[CodingAgentDeps]
    workspace: WorkspaceBackend | None = None


# Restate's ASGI handlers are not FastAPI path operations. The HTTP response
# bridge scopes FastAPI's resolved deps to that request; Agent.run gets deps explicitly.
CODING_AGENT_DEPS: ContextVar[CodingAgentDeps] = ContextVar("coding_agent_deps")
