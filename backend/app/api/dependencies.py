"""FastAPI dependencies for api routes."""

from __future__ import annotations

import logging
from functools import cache
from typing import TYPE_CHECKING, Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.blob_storage import BlobStorageClient, S3Client, VercelBlobClient
from app.clients.database import get_db_session
from app.clients.email import EmailClient, SMTPClient
from app.clients.issues import IssueStore, SQLIssueStore
from app.clients.pull_requests import PullRequestStore, SQLPullRequestStore
from app.clients.redis import AbstractRedisClient, RedisClient, UpstashRedisClient
from app.clients.repositories import RepositoryStore, SQLRepositoryStore
from app.clients.users import SQLUserStore, UserStore
from app.config import settings
from app.entities.users import User
from app.schemas.token import TokenPayload
from app.services.blob_backend import BlobBackend
from app.services.crud import CrudService
from app.services.issues import IssueService
from app.services.pull_requests import PullRequestService
from app.services.repositories import RepositoryService
from app.utils import security

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

logger = logging.getLogger(__name__)

reusable_oauth2 = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/login/access-token")


async def get_db() -> AsyncGenerator[AsyncSession]:
    """Get database session dependency.

    Yields:
        SQLAlchemy async session.
    """
    async with get_db_session() as session:
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
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
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


def get_crud_service(user_store: UserStoreDep) -> CrudService:
    """Get CRUD service dependency.

    Args:
        user_store: User store.

    Returns:
        CRUD service instance.
    """
    return CrudService(user_store)


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


def get_repository_service(
    backend: BackendDep,
    blob_client: BlobStorageClientDep,
    redis_client: RedisClientDep,
) -> RepositoryService:
    """Get the repository service dependency.

    Args:
        backend: Git backend dependency.
        blob_client: Blob storage client dependency.
        redis_client: Redis client dependency.

    Returns:
        Repository service instance.
    """
    return RepositoryService(backend, blob_client, redis_client)


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


def get_issue_service(issue_store: IssueStoreDep, repository_store: RepositoryStoreDep) -> IssueService:
    """Get the issue service dependency.

    Args:
        issue_store: Issue store dependency.
        repository_store: Repository store dependency.

    Returns:
        Issue service instance.
    """
    return IssueService(issue_store, repository_store)


IssueServiceDep = Annotated[IssueService, Depends(get_issue_service)]


def get_pull_request_service(
    pull_request_store: PullRequestStoreDep,
    repository_store: RepositoryStoreDep,
) -> PullRequestService:
    """Get the pull request service dependency.

    Args:
        pull_request_store: Pull request store dependency.
        repository_store: Repository store dependency.

    Returns:
        Pull request service instance.
    """
    return PullRequestService(pull_request_store, repository_store)


PullRequestServiceDep = Annotated[PullRequestService, Depends(get_pull_request_service)]
