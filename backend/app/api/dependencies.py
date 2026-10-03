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
from sqlalchemy.orm import Session

from app.clients.blob_storage import BlobStorageClient, S3Client, VercelBlobClient
from app.clients.database import get_db_session
from app.clients.email import EmailClient, SMTPClient
from app.clients.redis import AbstractRedisClient, RedisClient, UpstashRedisClient
from app.clients.repositories import RepositoryRepository, SQLRepositoryRepository
from app.clients.users import SQLUserRepository, UserRepository
from app.config import settings
from app.entities.users import User
from app.schemas.token import TokenPayload
from app.services.blob_backend import BlobBackend
from app.services.crud import CrudService
from app.utils import security

if TYPE_CHECKING:
    from collections.abc import Generator

logger = logging.getLogger(__name__)

reusable_oauth2 = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/login/access-token")


def get_db() -> Generator[Session]:
    """Get database session dependency.

    Yields:
        SQLAlchemy session.
    """
    with get_db_session() as session:
        yield session


SessionDep = Annotated[Session, Depends(get_db)]
TokenDep = Annotated[str, Depends(reusable_oauth2)]


def get_user_repository(session: SessionDep) -> UserRepository:
    """Get user repository dependency.

    Args:
        session: SQLAlchemy session.

    Returns:
        User repository instance.
    """
    return SQLUserRepository(session)


UserRepositoryDep = Annotated[UserRepository, Depends(get_user_repository)]


def get_repository_store(session: SessionDep) -> RepositoryRepository:
    """Get repository store dependency.

    Args:
        session: SQLAlchemy session.

    Returns:
        Repository store instance.
    """
    return SQLRepositoryRepository(session)


RepositoryRepositoryDep = Annotated[RepositoryRepository, Depends(get_repository_store)]


def get_current_user(user_repository: UserRepositoryDep, token: TokenDep) -> User:
    """Get the current authenticated user.

    Args:
        user_repository: User repository.
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
    user = user_repository.get(token_data.sub)
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


def get_crud_service(user_repository: UserRepositoryDep) -> CrudService:
    """Get CRUD service dependency.

    Args:
        user_repository: User repository.

    Returns:
        CRUD service instance.
    """
    return CrudService(user_repository)


CrudServiceDep = Annotated[CrudService, Depends(get_crud_service)]


def check_database_connection(session: SessionDep) -> bool:
    """Check if database connection is working.

    Args:
        session: SQLAlchemy session.

    Returns:
        True if connection works, False otherwise.
    """
    try:
        session.connection()  # don't close the connection, as it belongs to the session
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
