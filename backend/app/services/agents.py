"""Agent workspace orchestration and repository authorization."""

import os
import uuid
from typing import TYPE_CHECKING

from app._vendor.pydantic_ai_opencode.registry import MODEL_REGISTRIES
from app.agents.catalog import OPENCODE_SERVICES
from app.clients.agent_invocations import AgentInvocationClient, RestateInvocationClient
from app.config import AGENT_NATIVE_PROVIDERS, settings
from app.entities.agents import AgentEnvironment, AgentRun, AgentSession
from app.exceptions import ConflictError, InvalidInputError, NotFoundError
from app.schemas.agents import CredentialPublic, EnvironmentPublic, SessionPublic

if TYPE_CHECKING:
    from app.clients.agent_credentials import AgentCredentialStore
    from app.clients.agent_repositories import AgentRepositoryClient
    from app.clients.agents import AgentStore
    from app.clients.repositories import RepositoryStore
    from app.entities.users import User
    from app.schemas.agents import (
        CredentialCreate,
        EnvironmentCreate,
        EnvironmentUpdate,
        RunCreate,
        SessionCreate,
        SessionUpdate,
    )
    from app.services.authorization import AuthorizationService


class AgentService:
    """Authorize all collection members and keep provider credentials server-side."""

    def __init__(
        self,
        sources: AgentRepositoryClient,
        credentials: AgentCredentialStore,
        store: AgentStore,
        repositories: RepositoryStore,
        authorization: AuthorizationService,
        invocations: AgentInvocationClient | None = None,
    ) -> None:
        """Inject storage and the existing repository permission engine."""
        self.invocations = invocations or RestateInvocationClient()
        self.credentials = credentials
        self.sources = sources
        self.store = store
        self.repositories = repositories
        self.authorization = authorization

    async def environment(self, environment_id: uuid.UUID, user: User) -> AgentEnvironment:
        """Hide another user's environment and recheck all repository permissions."""
        environment = await self.store.environment(environment_id)
        if environment is None or environment.user_id != user.id:
            raise NotFoundError("Environment not found")
        for repo in await self.store.repositories(environment_id):
            await self.authorization.require(await self.repositories.get(repo), user, "repository:read")
        return environment

    async def session(self, session_id: uuid.UUID, user: User) -> AgentSession:
        """Authorize chat history, submissions, and event replay identically."""
        session = await self.store.get(session_id)
        if session.user_id != user.id:
            raise NotFoundError("Session not found")
        await self.environment(session.environment_id, user)
        return session

    async def create_environment(self, body: EnvironmentCreate, user: User) -> AgentEnvironment:
        """Create a private repository collection after checking every member."""
        repository_ids: list[uuid.UUID] = []
        for name in body.repositories:
            owner, separator, repository_name = name.partition("/")
            if not separator or not owner or not repository_name or "/" in repository_name:
                raise InvalidInputError("Repositories must use owner/name")
            repository = await self.repositories.get_by_owner_and_name(owner, repository_name)
            await self.authorization.require(repository, user)
            repository_ids.append(repository.id)
        environment = AgentEnvironment(
            id=uuid.uuid4(),
            user_id=user.id,
            name=body.name,
            setup_script=body.setup_script,
            instructions=body.instructions,
        )
        await self.sources.export(environment.id, repository_ids)
        await self.store.create_environment(environment, list(dict.fromkeys(repository_ids)))
        return environment

    async def create_session(self, body: SessionCreate, user: User) -> AgentSession:
        """Fork the prepared setup snapshot for an independent coding chat."""
        environment = await self.environment(body.environment_id, user)
        if body.kind == "coding" and not environment.snapshot_id:
            raise ConflictError("Complete an environment setup chat first")
        session = AgentSession(
            id=uuid.uuid4(),
            user_id=user.id,
            environment_id=environment.id,
            title=body.title,
            kind=body.kind,
            snapshot_id=environment.snapshot_id,
        )
        await self.store.add(session)
        return session

    async def submit(self, session_id: uuid.UUID, body: RunCreate, user: User) -> AgentRun:
        """Durably enqueue a turn; request IDs are scoped to the authorized chat."""
        session = await self.session(session_id, user)
        if session.archived:
            raise ConflictError("This chat is archived")
        provider, _, name = body.model.partition(":")
        if provider in OPENCODE_SERVICES:
            if name not in MODEL_REGISTRIES[OPENCODE_SERVICES[provider]]:
                raise InvalidInputError("Unknown OpenCode chat model")
            connected = await self.credentials.connection(user.id, provider)
            key = os.environ.get(f"GITEDGE_{provider.upper().replace('-', '_')}_API_KEY")
            if connected is None and not key:
                label = "OpenCode Zen" if provider == "opencode-zen" else "OpenCode Go"
                raise InvalidInputError(f"Connect {label} in AI credentials before using this model")
        elif body.model not in settings.AGENTS_MODELS and await self.credentials.connection(user.id, provider) is None:
            raise InvalidInputError("Model is not configured")
        turn = await self.store.request(session.id, str(body.request_id))
        if turn is None:
            turn = AgentRun(
                id=uuid.uuid5(session.id, str(body.request_id)),
                session_id=session.id,
                request_id=str(body.request_id),
                model=body.model,
                prompt=body.prompt,
                status="pending",
            )
            turn = await self.store.create_run(turn)
        if turn.prompt != body.prompt or turn.model != body.model:
            raise ConflictError("Request ID already used for a different turn")
        if turn.invocation_id:
            return turn
        turn.invocation_id = await self.invocations.submit(session.id, turn.id)
        await self.store.save_run(turn)
        return turn

    async def list_environments(self, user: User) -> list[EnvironmentPublic]:
        """Return collections with their repository names, never internal storage keys."""
        result = []
        for item in await self.store.environments(user.id):
            view = EnvironmentPublic.model_validate(item)
            view.repositories = await self.store.repository_names(item.id)
            result.append(view)
        return result

    async def list_sessions(self, user: User) -> list[SessionPublic]:
        """Include the active durable turn so a page refresh can reconnect."""
        result = []
        for item in await self.store.sessions(user.id):
            view = SessionPublic.model_validate(item)
            active = await self.store.active_run(item.id)
            view.active_run = active.id if active else None
            result.append(view)
        return result

    async def update_environment(
        self, environment_id: uuid.UUID, body: EnvironmentUpdate, user: User
    ) -> EnvironmentPublic:
        """Save setup configuration for future images without altering running forks."""
        environment = await self.environment(environment_id, user)
        await self.store.save_environment(environment, body.model_dump())
        return EnvironmentPublic.model_validate(environment)

    async def update_session(self, session_id: uuid.UUID, body: SessionUpdate, user: User) -> SessionPublic:
        """Rename, pin, or archive an owned conversation."""
        session = await self.session(session_id, user)
        if body.archived and await self.store.active_run(session_id):
            raise ConflictError("Wait for the active run before archiving this chat")
        await self.store.update(session, body.model_dump(exclude_none=True))
        return SessionPublic.model_validate(session)

    async def get_run(self, run_id: uuid.UUID, user: User) -> AgentRun:
        """Authorize status, terminal output, and notification mutations uniformly."""
        turn = await self.store.run(run_id)
        if turn is None:
            raise NotFoundError("Run not found")
        await self.session(turn.session_id, user)
        return turn

    async def provider_connections(self, user: User) -> list[CredentialPublic]:
        """List metadata only; encrypted keys have no read endpoint."""
        return [CredentialPublic.model_validate(item) for item in await self.credentials.list_for_user(user.id)]

    async def save_connection(self, provider: str, body: CredentialCreate, user: User) -> CredentialPublic:
        """Validate a provider and encrypt its account-owned connection."""
        allowed = {*AGENT_NATIVE_PROVIDERS, *settings.AGENTS_OPENAI_ENDPOINTS}
        if provider not in allowed:
            raise InvalidInputError("Provider is not configured")
        value = await self.credentials.save_secret(user.id, provider, body.label, body.secret.get_secret_value())
        return CredentialPublic.model_validate(value)
