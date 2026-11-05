"""Verify real PostgreSQL PAT persistence, collisions, rotation, and concurrent limits."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, override

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from app.clients.database import create_session_factory
from app.clients.personal_access_tokens import AUTHENTICATION_LIMIT, SQLPersonalAccessTokenStore
from app.clients.users import SQLUserStore
from app.entities.users import User
from app.exceptions import (
    InsufficientTokenRepositoryError,
    InsufficientTokenScopeError,
    InvalidPersonalAccessTokenError,
)
from app.schemas.personal_access_tokens import PersonalAccessTokenCreate, TokenScope
from app.services.personal_access_tokens import PersonalAccessTokenService
from tests.conftest import _run_async

if TYPE_CHECKING:
    from app.entities.personal_access_tokens import PersonalAccessToken


def test_personal_access_tokens_persistence(infrastructure: dict[str, str]) -> None:
    _run_async(check_personal_access_tokens(infrastructure["DATABASE_URL"]))


async def check_personal_access_tokens(database_url: str) -> None:
    engine = create_async_engine(database_url)
    factory = create_session_factory(engine)
    suffix = uuid.uuid4().hex
    try:
        async with factory() as db:
            users = SQLUserStore(db)
            owner = User(
                name=f"pat-{suffix}",
                lower_name=f"pat-{suffix}",
                email=f"pat-{suffix}@example.com",
                hashed_password="unused",
                is_active=True,
            )
            await users.add(owner)
            owner_id = owner.id
            store = SQLPersonalAccessTokenStore(db)
            service = PersonalAccessTokenService(store, users)
            body = PersonalAccessTokenCreate(
                name="Workstation", scopes=[TokenScope.WRITE], repository_ids=[uuid.uuid4()]
            )
            issued = await service.issue(body, owner)
            first_id, first_key_id = issued.id, issued.key_id
            row = await store.get(first_id)
            assert row.secret_hash.startswith("$argon2id$")
            assert row.secret_last4 == issued.token[-4:]
            authenticated = await service.authenticate(issued.token)
            assert authenticated.user is owner
            assert issued.repository_ids == body.repository_ids
            assert row.repository_ids == [str(repository_id) for repository_id in body.repository_ids]
            authenticated.require(body.repository_ids[0], TokenScope.WRITE)
            with pytest.raises(InsufficientTokenRepositoryError):
                authenticated.require(uuid.uuid4(), TokenScope.READ)
            with pytest.raises(InsufficientTokenScopeError):
                authenticated.require(body.repository_ids[0], TokenScope.ISSUES_WRITE)
            assert row.last_used_at is not None
            replacement = await service.rotate(first_id, body, owner)
            replacement_id = replacement.id
            assert (await store.get(first_id)).revoked_reason == "Rotated"
            with pytest.raises(InvalidPersonalAccessTokenError):
                await service.authenticate(issued.token)

            class CollidingStore(SQLPersonalAccessTokenStore):
                """Force one genuine unique-index collision during issuance."""

                attempts = 0

                @override
                async def issue(self, token: PersonalAccessToken, replacing: PersonalAccessToken | None = None) -> bool:
                    self.attempts += 1
                    if self.attempts == 1:
                        token.key_id = first_key_id
                    return await super().issue(token, replacing)

            colliding = CollidingStore(db)
            retried = await PersonalAccessTokenService(colliding, users).issue(body, owner)
            assert colliding.attempts == 2
            assert retried.id != first_id
            # Rollback during collision expires ORM objects: re-load by stable ids.
            owner = await users.get(owner_id)
            row = await store.get(replacement_id)
            row.authentication_window_start = None
            row.authentication_attempts = 0
            await store.update(row)

        now = datetime.now(UTC)

        async def reserve_attempt() -> bool:
            async with factory() as session:
                tokens = SQLPersonalAccessTokenStore(session)
                token = await tokens.get(replacement_id)
                return await tokens.reserve_authentication(token, now)

        results = await asyncio.gather(*(reserve_attempt() for _ in range(AUTHENTICATION_LIMIT + 10)))
        assert sum(results) == AUTHENTICATION_LIMIT
        async with factory() as db:
            users = SQLUserStore(db)
            owner = await users.get(owner_id)
            store = SQLPersonalAccessTokenStore(db)
            assert (await store.get(replacement_id)).authentication_attempts == AUTHENTICATION_LIMIT
            await PersonalAccessTokenService(store, users).revoke(replacement_id, owner, "Integration test")
            token = await store.get(replacement_id)
            assert token.revoked_at is not None
            assert not await store.reserve_authentication(token, now)
            await users.delete(owner)
            assert not await store.list_by_owner(owner_id)
    finally:
        await engine.dispose()
