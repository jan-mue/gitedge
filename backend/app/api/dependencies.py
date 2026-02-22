from collections.abc import Generator
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from loguru import logger
from pydantic import ValidationError
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.clients.database import get_db_session
from app.clients.email import EmailClient, SMTPClient
from app.clients.items import ItemRepository, SQLItemRepository
from app.clients.users import SQLUserRepository, UserRepository
from app.config import settings
from app.entities.users import User
from app.schemas.token import TokenPayload
from app.services.crud import CrudService
from app.utils import security

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/login/access-token"
)


def get_db() -> Generator[Session, None, None]:
    with get_db_session() as session:
        yield session


SessionDep = Annotated[Session, Depends(get_db)]
TokenDep = Annotated[str, Depends(reusable_oauth2)]


def get_user_repository(session: SessionDep) -> UserRepository:
    return SQLUserRepository(session)


UserRepositoryDep = Annotated[UserRepository, Depends(get_user_repository)]


def get_current_user(user_repository: UserRepositoryDep, token: TokenDep) -> User:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
    except (InvalidTokenError, ValidationError) as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        ) from e
    if not token_data.sub:
        raise HTTPException(status_code=403, detail="Could not validate credentials")
    user = user_repository.get(token_data.sub)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_current_active_superuser(current_user: CurrentUser) -> User:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )
    return current_user


def get_item_repository(session: SessionDep) -> ItemRepository:
    return SQLItemRepository(session)


ItemRepositoryDep = Annotated[ItemRepository, Depends(get_item_repository)]


def get_crud_service(
    user_repository: UserRepositoryDep, item_repository: ItemRepositoryDep
) -> CrudService:
    return CrudService(user_repository, item_repository)


CrudServiceDep = Annotated[CrudService, Depends(get_crud_service)]


def check_database_connection(session: SessionDep) -> bool:
    try:
        session.connection()  # don't close the connection, as it belongs to the session
    except DBAPIError:
        logger.error("Database connection error")
        return False
    else:
        return True


def get_email_client() -> EmailClient:
    return SMTPClient()


EmailClientDep = Annotated[EmailClient, Depends(get_email_client)]
