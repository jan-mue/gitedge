"""Agent workspace orchestration and repository authorization."""

import uuid
from typing import TYPE_CHECKING

import restate

from app.agents.runtime import run
from app.config import settings
from app.entities.agents import AgentEnvironment, AgentRun, AgentSession
from app.exceptions import ConflictError, InvalidInputError, NotFoundError

if TYPE_CHECKING:
    from app.clients.agent_repositories import AgentRepositoryClient
    from app.clients.agents import AgentStore
    from app.clients.repositories import RepositoryStore
    from app.entities.users import User
    from app.schemas.agents import EnvironmentCreate, RunCreate, SessionCreate
    from app.services.authorization import AuthorizationService


class AgentService:
    """Authorize all collection members and keep provider credentials server-side."""

    def __init__(
        self,
        sources: AgentRepositoryClient,
        store: AgentStore,
        repositories: RepositoryStore,
        authorization: AuthorizationService,
    ) -> None:
        """Inject storage and the existing repository permission engine."""
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
        if body.model not in settings.AGENTS_MODELS:
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
        headers = {"Authorization": f"Bearer {settings.RESTATE_AUTH_TOKEN}"} if settings.RESTATE_AUTH_TOKEN else {}
        async with restate.create_client(settings.RESTATE_INGRESS_URL, headers=headers) as client:
            handle = await client.object_send(run, key=str(session.id), arg=str(turn.id), idempotency_key=str(turn.id))
        turn.invocation_id = handle.invocation_id
        await self.store.save_run(turn)
        return turn
