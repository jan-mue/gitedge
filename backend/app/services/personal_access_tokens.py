"""Argon2id PAT issuance, verification, scoped authorization, and audit events."""

from __future__ import annotations

import logging
import re
import secrets
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from fastapi import BackgroundTasks, HTTPException
from fastapi.concurrency import run_in_threadpool
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError
from pwdlib.hashers.argon2 import Argon2Hasher

from app.entities.personal_access_tokens import PersonalAccessToken
from app.schemas.personal_access_tokens import GitScope, PersonalAccessTokenIssued, PersonalAccessTokenPublic

if TYPE_CHECKING:
    import uuid

    from app.clients.personal_access_tokens import PersonalAccessTokenStore
    from app.clients.users import UserStore
    from app.entities.users import User
    from app.schemas.personal_access_tokens import PersonalAccessTokenCreate

logger = logging.getLogger(__name__)
PAT_FORMAT_PREFIX = "gitedge_pat_live_v1_"
TOKEN_PATTERN = re.compile(r"gitedge_pat_live_v1_([0-9a-f]{24})\.([A-Za-z0-9_-]{43})\Z")
TOKEN_HASH = PasswordHash((Argon2Hasher(memory_cost=19456, time_cost=2, parallelism=1),))
ISSUANCE_ATTEMPTS = 5


def invalid_token() -> HTTPException:
    """Return a generic authentication error without credential details."""
    return HTTPException(
        status_code=401, detail="Invalid personal access token", headers={"WWW-Authenticate": 'Basic realm="GitEdge"'}
    )


class PersonalAccessTokenService:
    """Manage PATs and authenticate their owners without persisting plaintext."""

    def __init__(
        self, store: PersonalAccessTokenStore, users: UserStore, audit_tasks: BackgroundTasks | None = None
    ) -> None:
        """Initialize the token and owner stores."""
        self.store = store
        self.users = users
        self.audit_tasks = audit_tasks

    def audit(self, event: str, key_id: str, owner_id: uuid.UUID) -> None:
        """Schedule metadata-only audit logging outside the response path."""
        message = "PAT %s owner_id=%s key_id=%s"
        if self.audit_tasks is not None:
            self.audit_tasks.add_task(logger.info, message, event, owner_id, key_id)
        else:
            logger.info(message, event, owner_id, key_id)

    async def list_tokens(self, user: User) -> list[PersonalAccessTokenPublic]:
        """Return safe metadata belonging to the authenticated account."""
        return [PersonalAccessTokenPublic.model_validate(token) for token in await self.store.list_by_owner(user.id)]

    async def owned_token(self, token_id: uuid.UUID, user: User) -> PersonalAccessToken:
        """Resolve a token only within its owner's account."""
        token = await self.store.find(token_id)
        if token is None or token.owner_id != user.id:
            raise HTTPException(status_code=404, detail="Token not found")
        return token

    async def issue(
        self, body: PersonalAccessTokenCreate, user: User, replacing: PersonalAccessToken | None = None
    ) -> PersonalAccessTokenIssued:
        """Generate a public key identifier and 32 random bytes for the secret."""
        owner_id = user.id
        for _ in range(ISSUANCE_ATTEMPTS):
            key_id = secrets.token_hex(12)
            secret = secrets.token_urlsafe(32)
            secret_hash = await run_in_threadpool(TOKEN_HASH.hash, secret)
            token = PersonalAccessToken(
                owner_id=owner_id,
                name=body.name,
                prefix=PAT_FORMAT_PREFIX,
                key_id=key_id,
                secret_hash=secret_hash,
                secret_last4=secret[-4:],
                scopes=[str(scope) for scope in body.scopes],
                expires_at=body.expires_at,
                created_at=datetime.now(UTC),
            )
            if await self.store.issue(token, replacing):
                self.audit("rotated" if replacing is not None else "issued", key_id, owner_id)
                return PersonalAccessTokenIssued.from_token(
                    PersonalAccessTokenPublic.model_validate(token), f"{PAT_FORMAT_PREFIX}{key_id}.{secret}"
                )
        raise HTTPException(status_code=503, detail="Could not issue a token; try again")

    async def revoke(self, token_id: uuid.UUID, user: User, reason: str | None) -> None:
        """Revoke a credential idempotently, retaining its audit metadata."""
        token = await self.owned_token(token_id, user)
        if token.revoked_at is None:
            token.revoked_at = datetime.now(UTC)
            token.revoked_reason = reason
            await self.store.update(token)
            self.audit("revoked", token.key_id, user.id)

    async def rotate(
        self, token_id: uuid.UUID, body: PersonalAccessTokenCreate, user: User
    ) -> PersonalAccessTokenIssued:
        """Issue a replacement and revoke the old credential atomically."""
        token = await self.owned_token(token_id, user)
        if token.revoked_at is not None:
            raise HTTPException(status_code=409, detail="Token is already revoked")
        return await self.issue(body, user, token)

    async def authenticate(self, presented: str, scope: GitScope, username: str | None = None) -> User:
        """Verify format, state, Argon2id hash, owner, and operation scope."""
        match = TOKEN_PATTERN.fullmatch(presented)
        if match is None:
            raise invalid_token()
        key_id, secret = match.groups()
        token = await self.store.find_by_key_id(key_id)
        now = datetime.now(UTC)
        if (
            token is None
            or token.prefix != PAT_FORMAT_PREFIX
            or token.revoked_at is not None
            or (token.expires_at is not None and token.expires_at <= now)
        ):
            raise invalid_token()
        if not await self.store.reserve_authentication(token, now):
            raise HTTPException(
                status_code=429, detail="Token authentication limit reached", headers={"Retry-After": "60"}
            )
        try:
            verified, updated_hash = await run_in_threadpool(TOKEN_HASH.verify_and_update, secret, token.secret_hash)
        except UnknownHashError:
            logger.error("PAT hash invalid key_id=%s", key_id)
            raise invalid_token() from None
        if not verified:
            raise invalid_token()
        user = await self.users.find(token.owner_id)
        if user is None or not user.is_active or (username is not None and username.lower() != user.lower_name):
            raise invalid_token()
        # Read current state again after costly verification so a concurrent
        # revocation cannot authenticate using an earlier metadata snapshot.
        await self.store.refresh(token)
        if token.revoked_at is not None or (token.expires_at is not None and token.expires_at <= datetime.now(UTC)):
            raise invalid_token()
        if scope not in token.scopes and not (scope == GitScope.READ and GitScope.WRITE in token.scopes):
            raise HTTPException(status_code=403, detail="Token lacks the required Git scope")
        token.last_used_at = now
        if updated_hash is not None:
            token.secret_hash = updated_hash
        await self.store.update(token)
        self.audit(f"authenticated scope={scope}", key_id, user.id)
        return user
