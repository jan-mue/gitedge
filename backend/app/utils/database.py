"""Database initialization helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.clients.users import SQLUserStore
from app.config import settings
from app.schemas.users import UserCreate
from app.services.crud import CrudService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def init_db(session: AsyncSession) -> None:
    """Create the initial superuser if it does not already exist.

    Args:
        session: SQLAlchemy async session to use.
    """
    crud_service = CrudService(SQLUserStore(session))
    user = await crud_service.get_user_by_email(email=settings.FIRST_SUPERUSER)
    if not user:
        user_in = UserCreate(
            email=settings.FIRST_SUPERUSER,
            password=settings.FIRST_SUPERUSER_PASSWORD,
            is_superuser=True,
        )
        await crud_service.create_user(user_create=user_in)
