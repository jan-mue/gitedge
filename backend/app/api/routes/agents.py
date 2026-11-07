"""Authenticated workspace API; durable execution lives behind the Restate endpoint."""

import uuid
from typing import Annotated

from ag_ui.core import Message
from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic_ai.messages import ModelMessagesTypeAdapter
from pydantic_ai.ui.ag_ui import AGUIAdapter

from app.agents.runtime import stream_store
from app.api.dependencies import (
    AuthorizationServiceDep,
    BlobStorageClientDep,
    CurrentUser,
    GitClientDep,
    RepositoryStoreDep,
    SessionDep,
)
from app.clients.agent_credentials import AgentCredentialStore
from app.clients.agent_repositories import AgentRepositoryClient
from app.clients.agents import AgentStore
from app.config import settings
from app.schemas.agents import (
    CredentialCreate,
    CredentialPublic,
    EnvironmentCreate,
    EnvironmentPublic,
    EnvironmentUpdate,
    ProviderPublic,
    RunCreate,
    RunPublic,
    SessionCreate,
    SessionPublic,
    SessionUpdate,
)
from app.services.agents import AgentService


def enabled() -> None:
    """Keep deployment opt-in until Restate and sandbox infrastructure is configured."""
    if not settings.AGENTS_ENABLED:
        raise HTTPException(503, "GitEdge Agents is not configured")


router = APIRouter(prefix="/agents", tags=["agents"], dependencies=[Depends(enabled)])


def service(
    db: SessionDep,
    repositories: RepositoryStoreDep,
    authorization: AuthorizationServiceDep,
    git: GitClientDep,
    blobs: BlobStorageClientDep,
) -> AgentService:
    """Wire the service using the application's request-scoped stores."""
    return AgentService(
        AgentRepositoryClient(git, repositories, blobs),
        AgentCredentialStore(db),
        AgentStore(db),
        repositories,
        authorization,
    )


AgentServiceDep = Annotated[AgentService, Depends(service)]


@router.get("/models")
async def models(_user: CurrentUser) -> list[str]:
    """List configured provider-qualified model identifiers."""
    return settings.AGENTS_MODELS


@router.get("/environments")
async def environments(user: CurrentUser, agents: AgentServiceDep) -> list[EnvironmentPublic]:
    """List private repository collections."""
    return await agents.list_environments(user)


@router.post("/environments", status_code=201)
async def create_environment(body: EnvironmentCreate, user: CurrentUser, agents: AgentServiceDep) -> EnvironmentPublic:
    """Create a repository environment for a setup chat."""
    return EnvironmentPublic.model_validate(await agents.create_environment(body, user))


@router.get("/sessions")
async def sessions(user: CurrentUser, agents: AgentServiceDep) -> list[SessionPublic]:
    """List private conversations."""
    return await agents.list_sessions(user)


@router.post("/sessions", status_code=201)
async def create_session(body: SessionCreate, user: CurrentUser, agents: AgentServiceDep) -> SessionPublic:
    """Start setup or fork a coding conversation."""
    return SessionPublic.model_validate(await agents.create_session(body, user))


@router.post("/sessions/{session_id}/runs", status_code=202)
async def submit(session_id: uuid.UUID, body: RunCreate, user: CurrentUser, agents: AgentServiceDep) -> RunPublic:
    """Accept a durable turn without tying execution to this request."""
    return RunPublic.model_validate(await agents.submit(session_id, body, user))


@router.get("/runs/{run_id}")
async def status(run_id: uuid.UUID, user: CurrentUser, agents: AgentServiceDep) -> RunPublic:
    """Get an authorized turn status."""
    return RunPublic.model_validate(await agents.get_run(run_id, user))


@router.get("/runs/{run_id}/events")
async def events(
    run_id: uuid.UUID, user: CurrentUser, agents: AgentServiceDep, last_event_id: Annotated[str, Header()] = "0-0"
) -> StreamingResponse:
    """Replay stored AG-UI protocol events from Last-Event-ID."""
    await status(run_id, user, agents)
    return StreamingResponse(
        stream_store().read(str(run_id), last_event_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/notifications")
async def notifications(user: CurrentUser, agents: AgentServiceDep) -> list[RunPublic]:
    """Notify the owner when a cloud run finishes or fails."""
    return [RunPublic.model_validate(item) for item in await agents.store.notifications(user.id)]


@router.get("/sessions/{session_id}/messages")
async def messages(session_id: uuid.UUID, user: CurrentUser, agents: AgentServiceDep) -> list[Message]:
    """Read persisted conversation history in the same AG-UI format as live events."""
    await agents.session(session_id, user)
    history = ModelMessagesTypeAdapter.validate_python(await agents.store.history(session_id))
    return AGUIAdapter.dump_messages(history)


@router.put("/environments/{environment_id}")
async def update_environment(
    environment_id: uuid.UUID, body: EnvironmentUpdate, user: CurrentUser, agents: AgentServiceDep
) -> EnvironmentPublic:
    """Edit a setup script and instructions for the next setup run."""
    return await agents.update_environment(environment_id, body, user)


@router.patch("/sessions/{session_id}")
async def update_session(
    session_id: uuid.UUID, body: SessionUpdate, user: CurrentUser, agents: AgentServiceDep
) -> SessionPublic:
    """Persist chat names, pinning, and archiving."""
    return await agents.update_session(session_id, body, user)


@router.get("/sessions/{session_id}/runs")
async def runs(session_id: uuid.UUID, user: CurrentUser, agents: AgentServiceDep) -> list[RunPublic]:
    """Find durable invocations for reattachment after a refresh."""
    await agents.session(session_id, user)
    return [RunPublic.model_validate(item) for item in await agents.store.runs(session_id)]


@router.post("/runs/{run_id}/read", status_code=204)
async def read_notification(run_id: uuid.UUID, user: CurrentUser, agents: AgentServiceDep) -> None:
    """Dismiss a completed or failed run notification."""
    await agents.store.mark_read(await agents.get_run(run_id, user))


@router.get("/credentials")
async def credentials(user: CurrentUser, agents: AgentServiceDep) -> list[CredentialPublic]:
    """List provider connection metadata."""
    return await agents.provider_connections(user)


@router.put("/credentials/{provider}")
async def save_credentials(
    provider: str, body: CredentialCreate, user: CurrentUser, agents: AgentServiceDep
) -> CredentialPublic:
    """Replace an API key or ChatGPT connection file; secrets cannot be read back."""
    return await agents.save_connection(provider, body, user)


@router.delete("/credentials/{provider}", status_code=204)
async def remove_credentials(provider: str, user: CurrentUser, agents: AgentServiceDep) -> None:
    """Revoke this account's provider connection."""
    await agents.credentials.remove(user.id, provider)


@router.get("/providers")
async def providers(_user: CurrentUser) -> list[ProviderPublic]:
    """Discover configured native and OpenAI-compatible account providers."""
    names = {
        "openai": "OpenAI",
        "openai-chatgpt": "ChatGPT subscription",
        "anthropic": "Anthropic",
        "opencode-go": "OpenCode Go",
        "opencode-zen": "OpenCode Zen",
        "openrouter": "OpenRouter",
        "mistral": "Mistral",
        "vercel": "Vercel AI Gateway",
    }
    return [
        ProviderPublic(provider=key, label=names.get(key, key), auth="chatgpt" if key == "openai-chatgpt" else "key")
        for key in ["openai", "openai-chatgpt", "anthropic", *settings.AGENTS_OPENAI_ENDPOINTS]
    ]


@router.post("/runs/{run_id}/cancel", status_code=202)
async def cancel_run(run_id: uuid.UUID, user: CurrentUser, agents: AgentServiceDep) -> RunPublic:
    """Request a durable stop without tying cancellation to a browser connection."""
    turn = await agents.get_run(run_id, user)
    if turn.status in {"pending", "running"}:
        await stream_store().cancel(str(run_id))
    return RunPublic.model_validate(turn)
