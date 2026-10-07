"""FastAPI dependencies for api routes."""

from __future__ import annotations

import logging
from functools import cache
from typing import TYPE_CHECKING, Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.activity import ActivityStore, SQLActivityStore
from app.clients.blob_storage import BlobStorageClient, S3Client, VercelBlobClient
from app.clients.comments import CommentStore, SQLCommentStore
from app.clients.email import EmailClient, SMTPClient
from app.clients.issues import IssueStore, SQLIssueStore
from app.clients.organizations import OrganizationStore, SQLOrganizationStore
from app.clients.pull_requests import PullRequestStore, SQLPullRequestStore
from app.clients.redis import AbstractRedisClient, RedisClient, UpstashRedisClient
from app.clients.releases import ReleaseStore, SQLReleaseStore
from app.clients.repositories import RepositoryStore, SQLRepositoryStore
from app.clients.stars import SQLStarStore, StarStore
from app.clients.users import SQLUserStore, UserStore
from app.clients.watchers import SQLWatcherStore, WatcherStore
from app.config import settings
from app.entities.users import User
from app.schemas.token import TokenPayload
from app.services.activity import ActivityService
from app.services.blob_backend import BlobBackend
from app.services.comments import CommentService
from app.services.crud import CrudService
from app.services.forks import ForkService
from app.services.issues import IssueService
from app.services.organizations import OrganizationService
from app.services.pull_requests import PullRequestService
from app.services.releases import ReleaseService
from app.services.repositories import RepositoryService
from app.services.stars import StarService
from app.services.watchers import WatcherService
from app.utils import security

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from sqlalchemy.ext.asyncio import async_sessionmaker

logger = logging.getLogger(__name__)

reusable_oauth2 = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/login/access-token")


async def get_db(request: Request) -> AsyncGenerator[AsyncSession]:
    """Get database session dependency from the lifespan state.

    Args:
        request: The incoming request exposing the lifespan state.

    Yields:
        SQLAlchemy async session.
    """
    session_factory: async_sessionmaker[AsyncSession] = request.state.db_session_factory
    async with session_factory() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_db)]
TokenDep = Annotated[str, Depends(reusable_oauth2)]


def get_user_store(session: SessionDep) -> UserStore:
    """Get user store dependency.

    Args:
        session: SQLAlchemy session.

    Returns:
        User store instance.
    """
    return SQLUserStore(session)


UserStoreDep = Annotated[UserStore, Depends(get_user_store)]


def get_repository_store(session: SessionDep) -> RepositoryStore:
    """Get repository store dependency.

    Args:
        session: SQLAlchemy session.

    Returns:
        Repository store instance.
    """
    return SQLRepositoryStore(session)


RepositoryStoreDep = Annotated[RepositoryStore, Depends(get_repository_store)]


def get_organization_store(session: SessionDep) -> OrganizationStore:
    """Get organization store dependency.

    Args:
        session: SQLAlchemy session.

    Returns:
        Organization store instance.
    """
    return SQLOrganizationStore(session)


OrganizationStoreDep = Annotated[OrganizationStore, Depends(get_organization_store)]


async def get_current_user(user_store: UserStoreDep, token: TokenDep) -> User:
    """Get the current authenticated user.

    Args:
        user_store: User store.
        token: JWT token from request.

    Returns:
        The authenticated user.

    Raises:
        HTTPException: If authentication fails.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[security.ALGORITHM])
        token_data = TokenPayload(**payload)
    except (InvalidTokenError, ValidationError) as e:
        logger.error("Token decode error: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        ) from e
    if not token_data.sub:
        logger.error("Token has no sub claim")
        raise HTTPException(status_code=403, detail="Could not validate credentials")
    user = await user_store.get(token_data.sub)
    if not user:
        logger.error("User not found for id: %s", token_data.sub)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_current_active_superuser(current_user: CurrentUser) -> User:
    """Get the current user if they are a superuser.

    Args:
        current_user: The current authenticated user.

    Returns:
        The superuser.

    Raises:
        HTTPException: If user is not a superuser.
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="The user doesn't have enough privileges")
    return current_user


def get_crud_service(user_store: UserStoreDep, organization_store: OrganizationStoreDep) -> CrudService:
    """Get CRUD service dependency.

    Args:
        user_store: User store.
        organization_store: Organization store.

    Returns:
        CRUD service instance.
    """
    return CrudService(user_store, organization_store)


CrudServiceDep = Annotated[CrudService, Depends(get_crud_service)]


async def check_database_connection(session: SessionDep) -> bool:
    """Check if database connection is working.

    Args:
        session: SQLAlchemy async session.

    Returns:
        True if connection works, False otherwise.
    """
    try:
        await session.connection()  # don't close the connection, as it belongs to the session
    except SQLAlchemyError:
        logger.exception("Database connection error")
        return False
    else:
        return True


def get_email_client() -> EmailClient:
    """Get email client dependency.

    Returns:
        Email client instance.
    """
    return SMTPClient()


EmailClientDep = Annotated[EmailClient, Depends(get_email_client)]


@cache
def get_blob_client() -> BlobStorageClient:
    """Get blob storage client dependency.

    Returns:
        Blob storage client instance.
    """
    if settings.BLOB_STORAGE_KIND == "s3":
        return S3Client(
            endpoint=settings.S3_ENDPOINT or "",
            access_key=settings.S3_ACCESS_KEY or "",
            secret_key=settings.S3_SECRET_KEY or "",
            bucket=settings.S3_BUCKET or "gitedge",
            secure=settings.S3_SECURE,
        )
    return VercelBlobClient(token=settings.VERCEL_BLOB_TOKEN, access=settings.VERCEL_BLOB_ACCESS)


BlobStorageClientDep = Annotated[BlobStorageClient, Depends(get_blob_client)]


@cache
def get_redis_client() -> AbstractRedisClient:
    """Get the shared Redis client dependency.

    Returns:
        Redis client instance (standard or Upstash).
    """
    return UpstashRedisClient() if settings.REDIS_KIND == "rest" else RedisClient()


RedisClientDep = Annotated[AbstractRedisClient, Depends(get_redis_client)]


@cache
def get_backend() -> BlobBackend:
    """Get the shared Git backend instance.

    Returns:
        The shared BlobBackend instance.
    """
    return BlobBackend()


BackendDep = Annotated[BlobBackend, Depends(get_backend)]


def get_star_store(session: SessionDep) -> StarStore:
    """Get the star store dependency.

    Args:
        session: SQLAlchemy session.

    Returns:
        Star store instance.
    """
    return SQLStarStore(session)


StarStoreDep = Annotated[StarStore, Depends(get_star_store)]


def get_repository_service(
    backend: BackendDep,
    blob_client: BlobStorageClientDep,
    redis_client: RedisClientDep,
    repository_store: RepositoryStoreDep,
    star_store: StarStoreDep,
) -> RepositoryService:
    """Get the repository service dependency.

    Args:
        backend: Git backend dependency.
        blob_client: Blob storage client dependency.
        redis_client: Redis client dependency.
        repository_store: Repository store dependency.
        star_store: Star store dependency.

    Returns:
        Repository service instance.
    """
    return RepositoryService(backend, blob_client, redis_client, repository_store, star_store)


RepositoryServiceDep = Annotated[RepositoryService, Depends(get_repository_service)]


def get_issue_store(session: SessionDep) -> IssueStore:
    """Get the issue store dependency.

    Args:
        session: SQLAlchemy session.

    Returns:
        Issue store instance.
    """
    return SQLIssueStore(session)


IssueStoreDep = Annotated[IssueStore, Depends(get_issue_store)]


def get_pull_request_store(session: SessionDep) -> PullRequestStore:
    """Get the pull request store dependency.

    Args:
        session: SQLAlchemy session.

    Returns:
        Pull request store instance.
    """
    return SQLPullRequestStore(session)


PullRequestStoreDep = Annotated[PullRequestStore, Depends(get_pull_request_store)]


def get_watcher_store(session: SessionDep) -> WatcherStore:
    """Get the watcher store dependency.

    Args:
        session: SQLAlchemy session.

    Returns:
        Watcher store instance.
    """
    return SQLWatcherStore(session)


WatcherStoreDep = Annotated[WatcherStore, Depends(get_watcher_store)]


def get_comment_store(session: SessionDep) -> CommentStore:
    """Get the comment store dependency.

    Args:
        session: SQLAlchemy session.

    Returns:
        Comment store instance.
    """
    return SQLCommentStore(session)


CommentStoreDep = Annotated[CommentStore, Depends(get_comment_store)]


def get_release_store(session: SessionDep) -> ReleaseStore:
    """Get the release store dependency.

    Args:
        session: SQLAlchemy session.

    Returns:
        Release store instance.
    """
    return SQLReleaseStore(session)


ReleaseStoreDep = Annotated[ReleaseStore, Depends(get_release_store)]


def get_activity_store(session: SessionDep) -> ActivityStore:
    """Get the activity store dependency.

    Args:
        session: SQLAlchemy session.

    Returns:
        Activity store instance.
    """
    return SQLActivityStore(session)


ActivityStoreDep = Annotated[ActivityStore, Depends(get_activity_store)]


def get_activity_service(
    activity_store: ActivityStoreDep,
    repository_store: RepositoryStoreDep,
    star_store: StarStoreDep,
) -> ActivityService:
    """Get the activity service dependency.

    Args:
        activity_store: Activity store dependency.
        repository_store: Repository store dependency.
        star_store: Star store dependency.

    Returns:
        Activity service instance.
    """
    return ActivityService(activity_store, repository_store, star_store)


ActivityServiceDep = Annotated[ActivityService, Depends(get_activity_service)]


def get_issue_service(
    issue_store: IssueStoreDep,
    repository_store: RepositoryStoreDep,
    activity_service: ActivityServiceDep,
) -> IssueService:
    """Get the issue service dependency.

    Args:
        issue_store: Issue store dependency.
        repository_store: Repository store dependency.
        activity_service: Activity service dependency.

    Returns:
        Issue service instance.
    """
    return IssueService(issue_store, repository_store, activity_service)


IssueServiceDep = Annotated[IssueService, Depends(get_issue_service)]


def get_pull_request_service(
    pull_request_store: PullRequestStoreDep,
    repository_store: RepositoryStoreDep,
    repository_service: RepositoryServiceDep,
    activity_service: ActivityServiceDep,
) -> PullRequestService:
    """Get the pull request service dependency.

    Args:
        pull_request_store: Pull request store dependency.
        repository_store: Repository store dependency.
        repository_service: Repository service dependency.
        activity_service: Activity service dependency.

    Returns:
        Pull request service instance.
    """
    return PullRequestService(pull_request_store, repository_store, repository_service, activity_service)


PullRequestServiceDep = Annotated[PullRequestService, Depends(get_pull_request_service)]


def get_star_service(
    star_store: StarStoreDep,
    repository_store: RepositoryStoreDep,
    activity_service: ActivityServiceDep,
) -> StarService:
    """Get the star service dependency.

    Args:
        star_store: Star store dependency.
        repository_store: Repository store dependency.
        activity_service: Activity service dependency.

    Returns:
        Star service instance.
    """
    return StarService(star_store, repository_store, activity_service)


StarServiceDep = Annotated[StarService, Depends(get_star_service)]


def get_watcher_service(
    watcher_store: WatcherStoreDep,
    repository_store: RepositoryStoreDep,
    activity_service: ActivityServiceDep,
) -> WatcherService:
    """Get the watcher service dependency.

    Args:
        watcher_store: Watcher store dependency.
        repository_store: Repository store dependency.
        activity_service: Activity service dependency.

    Returns:
        Watcher service instance.
    """
    return WatcherService(watcher_store, repository_store, activity_service)


WatcherServiceDep = Annotated[WatcherService, Depends(get_watcher_service)]


def get_comment_service(
    *,
    comment_store: CommentStoreDep,
    issue_store: IssueStoreDep,
    pull_request_store: PullRequestStoreDep,
    repository_store: RepositoryStoreDep,
    activity_service: ActivityServiceDep,
) -> CommentService:
    """Get the comment service dependency.

    Args:
        comment_store: Comment store dependency.
        issue_store: Issue store dependency.
        pull_request_store: Pull request store dependency.
        repository_store: Repository store dependency.
        activity_service: Activity service dependency.

    Returns:
        Comment service instance.
    """
    return CommentService(
        comment_store=comment_store,
        issue_store=issue_store,
        pull_request_store=pull_request_store,
        repository_store=repository_store,
        activity_service=activity_service,
    )


CommentServiceDep = Annotated[CommentService, Depends(get_comment_service)]


def get_release_service(
    release_store: ReleaseStoreDep,
    repository_store: RepositoryStoreDep,
    activity_service: ActivityServiceDep,
) -> ReleaseService:
    """Get the release service dependency.

    Args:
        release_store: Release store dependency.
        repository_store: Repository store dependency.
        activity_service: Activity service dependency.

    Returns:
        Release service instance.
    """
    return ReleaseService(release_store, repository_store, activity_service)


ReleaseServiceDep = Annotated[ReleaseService, Depends(get_release_service)]


def get_fork_service(
    repository_store: RepositoryStoreDep,
    repository_service: RepositoryServiceDep,
    activity_service: ActivityServiceDep,
    star_store: StarStoreDep,
) -> ForkService:
    """Get the fork service dependency.

    Args:
        repository_store: Repository store dependency.
        repository_service: Repository service dependency.
        activity_service: Activity service dependency.
        star_store: Star store dependency.

    Returns:
        Fork service instance.
    """
    return ForkService(repository_store, repository_service, activity_service, star_store)


ForkServiceDep = Annotated[ForkService, Depends(get_fork_service)]


def get_organization_service(
    organization_store: OrganizationStoreDep,
    user_store: UserStoreDep,
) -> OrganizationService:
    """Get the organization service dependency.

    Args:
        organization_store: Organization store dependency.
        user_store: User store dependency.

    Returns:
        Organization service instance.
    """
    return OrganizationService(organization_store, user_store)


OrganizationServiceDep = Annotated[OrganizationService, Depends(get_organization_service)]
