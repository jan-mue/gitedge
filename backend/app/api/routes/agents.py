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
from app.clients.agent_repositories import AgentRepositoryClient
from app.clients.agents import AgentStore
from app.config import settings
from app.exceptions import NotFoundError
from app.schemas.agents import EnvironmentCreate, EnvironmentPublic, RunCreate, RunPublic, SessionCreate, SessionPublic
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
    return AgentService(AgentRepositoryClient(git, repositories, blobs), AgentStore(db), repositories, authorization)


AgentServiceDep = Annotated[AgentService, Depends(service)]


@router.get("/models")
async def models(_user: CurrentUser) -> list[str]:
    """List configured provider-qualified model identifiers."""
    return settings.AGENTS_MODELS


@router.get("/environments")
async def environments(user: CurrentUser, agents: AgentServiceDep) -> list[EnvironmentPublic]:
    """List private repository collections."""
    return [EnvironmentPublic.model_validate(item) for item in await agents.store.environments(user.id)]


@router.post("/environments", status_code=201)
async def create_environment(body: EnvironmentCreate, user: CurrentUser, agents: AgentServiceDep) -> EnvironmentPublic:
    """Create a repository environment for a setup chat."""
    return EnvironmentPublic.model_validate(await agents.create_environment(body, user))


@router.get("/sessions")
async def sessions(user: CurrentUser, agents: AgentServiceDep) -> list[SessionPublic]:
    """List private conversations."""
    return [SessionPublic.model_validate(item) for item in await agents.store.sessions(user.id)]


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
    turn = await agents.store.run(run_id)
    if turn is None:
        raise NotFoundError("Run not found")
    await agents.session(turn.session_id, user)
    return RunPublic.model_validate(turn)


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
