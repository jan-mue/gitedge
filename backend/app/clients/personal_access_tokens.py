"""PostgreSQL persistence and atomic rate limits for PATs."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import timedelta
from typing import TYPE_CHECKING

from sqlalchemy import case, or_, select, update
from sqlalchemy.exc import IntegrityError

from app.clients.database import CrudStore, SQLStore
from app.entities.personal_access_tokens import PersonalAccessToken

if TYPE_CHECKING:
    import uuid
    from datetime import datetime

    from sqlalchemy.ext.asyncio import AsyncSession

AUTHENTICATION_LIMIT = 60
AUTHENTICATION_WINDOW = timedelta(minutes=1)


class PersonalAccessTokenStore(CrudStore[PersonalAccessToken], ABC):
    """Store contract for token lifecycle and authentication."""

    @abstractmethod
    async def find_by_key_id(self, key_id: str) -> PersonalAccessToken | None:
        """Find the credential by its public identifier."""

    @abstractmethod
    async def list_by_owner(self, owner_id: uuid.UUID) -> list[PersonalAccessToken]:
        """List metadata for one account, including revoked tokens."""

    @abstractmethod
    async def issue(self, token: PersonalAccessToken, replacing: PersonalAccessToken | None = None) -> bool:
        """Persist issuance and optional rotation atomically; return false for a key-id collision."""

    @abstractmethod
    async def reserve_authentication(self, token: PersonalAccessToken, now: datetime) -> bool:
        """Atomically reserve one authentication attempt in the per-key window."""


class SQLPersonalAccessTokenStore(PersonalAccessTokenStore, SQLStore[PersonalAccessToken]):
    """SQLAlchemy-backed token store."""

    def __init__(self, db: AsyncSession) -> None:
        """Bind token operations to a database session."""
        super().__init__(db, PersonalAccessToken)

    async def find_by_key_id(self, key_id: str) -> PersonalAccessToken | None:
        """Look up a token without scanning hashes."""
        return await self.db.scalar(select(PersonalAccessToken).where(PersonalAccessToken.key_id == key_id))

    async def list_by_owner(self, owner_id: uuid.UUID) -> list[PersonalAccessToken]:
        """List account tokens newest first."""
        return list(
            await self.db.scalars(
                select(PersonalAccessToken)
                .where(PersonalAccessToken.owner_id == owner_id)
                .order_by(PersonalAccessToken.created_at.desc())
            )
        )

    async def issue(self, token: PersonalAccessToken, replacing: PersonalAccessToken | None = None) -> bool:
        """Issue and optionally revoke the previous credential in one transaction."""
        self.db.add(token)
        try:
            # Flush issuance before modifying the old row, so a key-id collision
            # rolls back without changing rotation state on the old credential.
            await self.db.flush()
            if replacing is not None:
                replacing.revoked_at = token.created_at
                replacing.revoked_reason = "Rotated"
            await self.db.commit()
        except IntegrityError as error:
            await self.db.rollback()
            if getattr(error.orig, "sqlstate", None) == "23505" and getattr(
                getattr(error.orig, "diag", None), "constraint_name", None
            ) in ("personal_access_token_key_id_key", "personal_access_token_key_id_idx"):
                return False
            raise
        await self.db.refresh(token)
        return True

    async def reserve_authentication(self, token: PersonalAccessToken, now: datetime) -> bool:
        """Use a conditional UPDATE so concurrent workers share one attempt limit."""
        expired_window = or_(
            PersonalAccessToken.authentication_window_start.is_(None),
            PersonalAccessToken.authentication_window_start <= now - AUTHENTICATION_WINDOW,
        )
        statement = (
            update(PersonalAccessToken)
            .where(
                PersonalAccessToken.id == token.id,
                or_(expired_window, PersonalAccessToken.authentication_attempts < AUTHENTICATION_LIMIT),
                PersonalAccessToken.revoked_at.is_(None),
            )
            .values(
                authentication_window_start=case(
                    (expired_window, now), else_=PersonalAccessToken.authentication_window_start
                ),
                authentication_attempts=case(
                    (expired_window, 1), else_=PersonalAccessToken.authentication_attempts + 1
                ),
            )
            .returning(PersonalAccessToken.id)
        )
        reserved = await self.db.scalar(statement)
        await self.db.commit()
        return reserved is not None
