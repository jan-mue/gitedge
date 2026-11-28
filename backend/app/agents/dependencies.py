"""Restate injection, call-scoped dependency chains, and explicit PydanticAI resources."""

import inspect
import uuid
from collections.abc import AsyncGenerator  # noqa: TC003 - uncalled-for evaluates chained provider annotations
from contextlib import asynccontextmanager
from dataclasses import dataclass
from functools import wraps
from typing import TYPE_CHECKING, Annotated

from fastapi import BackgroundTasks
from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.models import Model
from pydantic_ai_harness.docker_sandbox import DockerSandbox
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from uncalled_for import (
    CallArgument,
    Depends,
    FailedDependency,
    get_dependency_parameters,
    resolved_dependencies,
    without_dependencies,
)
from upstash_redis.asyncio import Redis as UpstashRedis
from vercel.sandbox import SandboxClient

from app.agents.providers import account_model
from app.clients.activity import ActivityStore, SQLActivityStore
from app.clients.agent_repositories import AgentRepositoryClient
from app.clients.agent_streams import AgentStreamStore
from app.clients.agents import AgentStore
from app.clients.authorization import AuthorizationStore, SQLAuthorizationStore
from app.clients.blob_storage import BlobStorageClient, S3Client, VercelBlobClient
from app.clients.cache import (
    AbstractCacheClient,
    NoopCacheClient,
    RedisCacheClient,
    VercelCacheClient,
    cache_backend_kind,
)
from app.clients.database import create_db_engine, create_session_factory
from app.clients.email import EmailClient, SMTPClient
from app.clients.git.blob_backend import BlobBackend
from app.clients.git.merges import GitMergeClient
from app.clients.git.repositories import GitClient
from app.clients.git.storage import RepositoryStorage
from app.clients.issues import IssueStore, SQLIssueStore
from app.clients.notifications import NotificationStore, SQLNotificationStore
from app.clients.organizations import OrganizationStore, SQLOrganizationStore
from app.clients.pull_requests import PullRequestStore, SQLPullRequestStore
from app.clients.redis import AbstractRedisClient, RedisClient, UpstashRedisClient
from app.clients.repositories import RepositoryStore, SQLRepositoryStore
from app.clients.stars import SQLStarStore, StarStore
from app.clients.users import SQLUserStore, UserStore
from app.config import settings
from app.sandboxes.vercel import VercelSandbox
from app.schemas.agent_turns import AgentTurnRequest
from app.services.activity import ActivityService
from app.services.agent_forge import AgentForgeService
from app.services.authorization import AuthorizationService
from app.services.issues import IssueService
from app.services.notifications import NotificationService
from app.services.pull_requests import PullRequestService
from app.services.repositories import RepositoryService

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from app.clients.agent_streams import AgentEventStore


def inject[**P, R](function: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
    """Resolve dependencies while retaining Restate's typed, positional handler interface.

    Dependencies are hidden from discovery, but explicit keyword values override
    them in tests. Uncalled-for owns call-scoped caching and async cleanup.
    """
    injected = without_dependencies(function)
    original = inspect.signature(function, eval_str=True)
    public = inspect.signature(injected)
    public = public.replace(
        parameters=[original.parameters.get(parameter.name, parameter) for parameter in public.parameters.values()],
        return_annotation=original.return_annotation,
    )
    dependencies = get_dependency_parameters(function)

    @wraps(function)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        overrides = {name: kwargs.pop(name) for name in dependencies if name in kwargs}
        arguments = public.bind(*args, **kwargs)
        return await injected(**arguments.arguments, **overrides)

    wrapper.__signature__ = public  # ty: ignore[missing-attribute] - standard Python callable signature metadata
    return wrapper


@dataclass(frozen=True, kw_only=True)
class AgentForgeScope:
    """Server-selected identity and repositories for one coding conversation."""

    user_id: uuid.UUID
    session_id: uuid.UUID
    repository_ids: tuple[uuid.UUID, ...]


@dataclass(kw_only=True)
class AgentDeps:
    """Common agent resources without a sandbox, suitable for a future chat agent."""

    streams: AgentEventStore
    blobs: BlobStorageClient


@dataclass(kw_only=True)
class SetupAgentDeps(AgentDeps):
    """Setup agents receive a sandbox but no forge operations."""

    sandbox: AbstractCapability[SetupAgentDeps]


@dataclass(kw_only=True)
class CodingAgentDeps(AgentDeps):
    """Coding-only dependencies always include authorized forge access."""

    sandbox: AbstractCapability[CodingAgentDeps]
    forge: AgentForgeService
    forge_scope: AgentForgeScope


SessionFactoryDep = Annotated[
    async_sessionmaker[AsyncSession], Depends(create_session_factory, engine=Depends(create_db_engine))
]


@asynccontextmanager
async def get_session(factory: SessionFactoryDep) -> AsyncGenerator[AsyncSession]:
    """Keep one session and its engine on the current handler's event loop."""
    async with factory() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_agent_store(session: SessionDep) -> AgentStore:
    """Keep store construction inside the dependency graph, not SDK signature introspection."""
    return AgentStore(session)


AgentStoreDep = Annotated[AgentStore, Depends(get_agent_store)]
UserStoreDep = Annotated[UserStore, Depends(SQLUserStore, db=Depends(get_session))]
RepositoryStoreDep = Annotated[RepositoryStore, Depends(SQLRepositoryStore, db=Depends(get_session))]
OrganizationStoreDep = Annotated[OrganizationStore, Depends(SQLOrganizationStore, db=Depends(get_session))]
AuthorizationStoreDep = Annotated[AuthorizationStore, Depends(SQLAuthorizationStore, db=Depends(get_session))]
IssueStoreDep = Annotated[IssueStore, Depends(SQLIssueStore, db=Depends(get_session))]
PullRequestStoreDep = Annotated[PullRequestStore, Depends(SQLPullRequestStore, db=Depends(get_session))]
ActivityStoreDep = Annotated[ActivityStore, Depends(SQLActivityStore, db=Depends(get_session))]
NotificationStoreDep = Annotated[NotificationStore, Depends(SQLNotificationStore, db=Depends(get_session))]
StarStoreDep = Annotated[StarStore, Depends(SQLStarStore, db=Depends(get_session))]


def get_authorization(
    store: AuthorizationStoreDep,
    repositories: RepositoryStoreDep,
    organizations: OrganizationStoreDep,
    users: UserStoreDep,
) -> AuthorizationService:
    """Resolve current account permissions from call-scoped stores."""
    return AuthorizationService(store, repositories, organizations, users)


AuthorizationDep = Annotated[AuthorizationService, Depends(get_authorization)]


@asynccontextmanager
async def get_tcp_redis() -> AsyncGenerator[Redis | None]:
    """Own the native socket pool for this call, never a process-wide event loop."""
    if settings.REDIS_KIND == "rest":
        yield None
    else:
        async with Redis.from_url(
            settings.REDIS_URL, password=settings.REDIS_PASSWORD, decode_responses=False
        ) as client:
            yield client


@asynccontextmanager
async def get_http_redis() -> AsyncGenerator[UpstashRedis | None]:
    """Close the serverless Redis transport on the same loop that created it."""
    if settings.REDIS_KIND != "rest":
        yield None
        return
    client = UpstashRedis(url=settings.REDIS_URL, token=settings.REDIS_PASSWORD or "")
    try:
        yield client
    finally:
        await client.close()


TCPRedisDep = Annotated[Redis | None, Depends(get_tcp_redis)]
HTTPRedisDep = Annotated[UpstashRedis | None, Depends(get_http_redis)]


def get_streams(tcp: TCPRedisDep, http: HTTPRedisDep) -> AgentStreamStore:
    """Share the call's transport between durable output and cancellation."""
    if http is not None:
        return AgentStreamStore(http)
    if tcp is None:
        raise ValueError("No Redis transport is configured")
    return AgentStreamStore(tcp)


StreamsDep = Annotated[AgentStreamStore, Depends(get_streams)]


def get_ref_redis(tcp: TCPRedisDep, http: HTTPRedisDep) -> AbstractRedisClient:
    """Adapt the same transport for Git object/ref storage."""
    if http is not None:
        return UpstashRedisClient(http)
    if tcp is None:
        raise ValueError("No Redis transport is configured")
    return RedisClient(tcp)


RedisDep = Annotated[AbstractRedisClient, Depends(get_ref_redis)]


def get_cache(tcp: TCPRedisDep) -> AbstractCacheClient:
    """Use the configured derived-data cache without HTTP request state."""
    kind = cache_backend_kind()
    if kind == "vercel":
        return VercelCacheClient(settings.CACHE_NAMESPACE)
    if kind == "redis" and tcp is not None:
        return RedisCacheClient(tcp)
    return NoopCacheClient()


CacheDep = Annotated[AbstractCacheClient, Depends(get_cache)]


@asynccontextmanager
async def get_blobs() -> AsyncGenerator[BlobStorageClient]:
    """Keep blob transports local to the executing handler."""
    if settings.BLOB_STORAGE_KIND == "s3":
        yield S3Client(
            endpoint=settings.S3_ENDPOINT or "",
            access_key=settings.S3_ACCESS_KEY or "",
            secret_key=settings.S3_SECRET_KEY or "",
            bucket=settings.S3_BUCKET or "gitedge",
            secure=settings.S3_SECURE,
        )
    else:
        client = VercelBlobClient(token=settings.VERCEL_BLOB_TOKEN, access=settings.VERCEL_BLOB_ACCESS)
        try:
            yield client
        finally:
            await client.aclose()


BlobsDep = Annotated[BlobStorageClient, Depends(get_blobs)]
BackendDep = Annotated[BlobBackend, Depends(BlobBackend)]


def get_git(
    backend: BackendDep, blobs: BlobsDep, redis: RedisDep, cache: CacheDep, repositories: RepositoryStoreDep
) -> GitClient:
    """Wire publication and repository access using this call's storage resources."""

    async def exists(owner: str, name: str) -> bool:
        return await repositories.find_by_owner_and_name(owner, name) is not None

    return GitClient(backend, RepositoryStorage(blobs, redis), cache, exists)


GitDep = Annotated[GitClient, Depends(get_git)]


@asynccontextmanager
async def get_background_tasks() -> AsyncGenerator[BackgroundTasks]:
    """Complete queued notification deliveries before dependent resources are closed."""
    tasks = BackgroundTasks()
    yield tasks
    await tasks()


BackgroundTasksDep = Annotated[BackgroundTasks, Depends(get_background_tasks)]
EmailDep = Annotated[EmailClient, Depends(SMTPClient)]


def get_notifications(
    store: NotificationStoreDep,
    repositories: RepositoryStoreDep,
    email: EmailDep,
    tasks: BackgroundTasksDep,
    authorization: AuthorizationDep,
) -> NotificationService:
    """Provide repository notifications independently of FastAPI background dependencies."""
    return NotificationService(store, repositories, email, tasks, authorization)


NotificationsDep = Annotated[NotificationService, Depends(get_notifications)]


def get_activity(
    store: ActivityStoreDep,
    repositories: RepositoryStoreDep,
    stars: StarStoreDep,
    authorization: AuthorizationDep,
    notifications: NotificationsDep,
) -> ActivityService:
    """Compose normal activity behavior from the Restate graph."""
    return ActivityService(store, repositories, stars, authorization, notifications)


ActivityDep = Annotated[ActivityService, Depends(get_activity)]


def get_repository_service(
    git: GitDep, cache: CacheDep, repositories: RepositoryStoreDep, stars: StarStoreDep, authorization: AuthorizationDep
) -> RepositoryService:
    """Bind Git reads and repository metadata."""
    return RepositoryService(git, cache, repositories, stars, authorization)


RepositoriesDep = Annotated[RepositoryService, Depends(get_repository_service)]


def get_merges(blobs: BlobsDep, redis: RedisDep, cache: CacheDep, backend: BackendDep) -> GitMergeClient:
    """Provide normal PR mergeability reads."""
    return GitMergeClient(blobs, redis, cache, backend)


MergesDep = Annotated[GitMergeClient, Depends(get_merges)]


def get_pulls(
    store: PullRequestStoreDep,
    repositories: RepositoryStoreDep,
    service: RepositoriesDep,
    activity: ActivityDep,
    merges: MergesDep,
    authorization: AuthorizationDep,
) -> PullRequestService:
    """Reuse PR business logic, not HTTP dependency wiring."""
    return PullRequestService(store, repositories, service, activity, merges, authorization)


PullsDep = Annotated[PullRequestService, Depends(get_pulls)]


def get_issues(
    store: IssueStoreDep, repositories: RepositoryStoreDep, activity: ActivityDep, authorization: AuthorizationDep
) -> IssueService:
    """Reuse issue business logic through chained dependencies."""
    return IssueService(store, repositories, activity, authorization)


IssuesDep = Annotated[IssueService, Depends(get_issues)]


def get_sources(git: GitDep, repositories: RepositoryStoreDep, blobs: BlobsDep) -> AgentRepositoryClient:
    """Publish credential-free workspace bundles through backend Git storage."""
    return AgentRepositoryClient(git, repositories, blobs)


SourcesDep = Annotated[AgentRepositoryClient, Depends(get_sources)]


def get_forge(
    sources: SourcesDep,
    repositories: RepositoryStoreDep,
    users: UserStoreDep,
    authorization: AuthorizationDep,
    pulls: PullsDep,
    issues: IssuesDep,
) -> AgentForgeService:
    """Resolve the server-side forge capability's authorization and domain services."""
    return AgentForgeService(sources, repositories, users, authorization, pulls, issues)


ForgeDep = Annotated[AgentForgeService, Depends(get_forge)]


@asynccontextmanager
async def get_vercel_client() -> AsyncGenerator[SandboxClient | None]:
    """Give the Vercel capability a dedicated, correctly scoped client."""
    if settings.AGENTS_SANDBOX != "vercel":
        yield None
        return
    client = SandboxClient.create()
    try:
        yield client
    finally:
        await client.aclose()


VercelClientDep = Annotated[SandboxClient | None, Depends(get_vercel_client)]


def get_sandbox[AgentDepsT: AgentDeps](vercel: VercelClientDep) -> AbstractCapability[AgentDepsT]:
    """Select the configured upstream capability using call-scoped resources."""
    if vercel is not None:
        return VercelSandbox(client=vercel)
    if settings.AGENTS_SANDBOX == "docker":
        return DockerSandbox(
            image=settings.AGENTS_DOCKER_IMAGE,
            allow_internet_access=settings.AGENTS_DOCKER_ALLOW_INTERNET_ACCESS,
            docker_args=(
                "--cpus",
                str(settings.AGENTS_DOCKER_CPUS),
                "--memory",
                f"{settings.AGENTS_DOCKER_MEMORY_MB}m",
            ),
        )
    from pydantic_ai_harness.smol_sandbox import SmolSandbox  # noqa: PLC0415

    return SmolSandbox(
        image=settings.AGENTS_SMOL_IMAGE,
        cpus=settings.AGENTS_SMOL_CPUS,
        memory_mb=settings.AGENTS_SMOL_MEMORY_MB,
        allow_internet_access=settings.AGENTS_SMOL_ALLOW_INTERNET_ACCESS,
    )


SetupSandboxDep = Annotated[AbstractCapability[SetupAgentDeps], Depends(get_sandbox)]
CodingSandboxDep = Annotated[AbstractCapability[CodingAgentDeps], Depends(get_sandbox)]


def get_agent_deps(streams: StreamsDep, blobs: BlobsDep) -> AgentDeps:
    """Resolve common resources independently of compute or forge capabilities."""
    return AgentDeps(streams=streams, blobs=blobs)


AgentDepsDep = Annotated[AgentDeps, Depends(get_agent_deps)]


def get_setup_deps(common: AgentDepsDep, sandbox: SetupSandboxDep) -> SetupAgentDeps:
    """Add only the sandbox resources required by environment setup."""
    return SetupAgentDeps(streams=common.streams, blobs=common.blobs, sandbox=sandbox)


SetupDepsDep = Annotated[SetupAgentDeps, Depends(get_setup_deps)]


@dataclass(kw_only=True)
class AgentSessionDeps:
    """Stores and compute resources for one authorized conversation invocation."""

    store: AgentStore
    users: UserStore
    repositories: RepositoryStore
    authorization: AuthorizationService
    agent: SetupAgentDeps


def get_session_deps(
    store: AgentStoreDep,
    users: UserStoreDep,
    repositories: RepositoryStoreDep,
    authorization: AuthorizationDep,
    agent: SetupDepsDep,
) -> AgentSessionDeps:
    """Cache common stores and resources once within this invocation's dependency chain."""
    return AgentSessionDeps(
        store=store, users=users, repositories=repositories, authorization=authorization, agent=agent
    )


AgentSessionDepsDep = Annotated[AgentSessionDeps, Depends(get_session_deps)]
TurnRequestDep = Annotated[AgentTurnRequest, CallArgument("request")]


def get_forge_scope(request: TurnRequestDep) -> AgentForgeScope:
    """Construct immutable forge scope from the server-authorized turn input."""
    return AgentForgeScope(
        user_id=request.user_id,
        session_id=uuid.UUID(request.session_id),
        repository_ids=tuple(request.repository_ids),
    )


ForgeScopeDep = Annotated[AgentForgeScope, Depends(get_forge_scope)]


def get_coding_deps(
    common: AgentDepsDep, sandbox: CodingSandboxDep, forge: ForgeDep, scope: ForgeScopeDep
) -> CodingAgentDeps:
    """Resolve complete coding resources without creating a partially initialized run."""
    return CodingAgentDeps(streams=common.streams, blobs=common.blobs, sandbox=sandbox, forge=forge, forge_scope=scope)


@asynccontextmanager
async def get_run_deps(request: TurnRequestDep) -> AsyncGenerator[SetupAgentDeps | CodingAgentDeps]:
    """Resolve only the selected agent's dependency chain for the full handler lifetime."""
    factory = get_coding_deps if request.coding else get_setup_deps
    async with resolved_dependencies(factory, {"request": request}) as arguments:
        for value in arguments.values():
            if isinstance(value, FailedDependency):
                raise value.error
        yield factory(**arguments)


RunDepsDep = Annotated[SetupAgentDeps | CodingAgentDeps, Depends(get_run_deps)]


@asynccontextmanager
async def get_account_model(request: TurnRequestDep, factory: SessionFactoryDep) -> AsyncGenerator[Model]:
    """Resolve account credentials from the trusted turn input outside the durable journal."""
    async with account_model(request.model, request.user_id, factory, session_id=request.session_id) as model, model:
        yield model


AccountModelDep = Annotated[Model, Depends(get_account_model)]
