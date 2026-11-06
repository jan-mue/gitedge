"""Safe PAT metadata and one-time issuance responses."""

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Self

from pydantic import AwareDatetime, ConfigDict, Field, field_validator

from app.schemas.base import GitEdgeBaseModel


class TokenScope(StrEnum):
    """Operations a personal access token can authorize."""

    ACTIONS_READ = "actions:read"
    ACTIONS_WRITE = "actions:write"
    READ = "git:read"
    WRITE = "git:write"
    REPOSITORY_READ = "repository:read"
    REPOSITORY_WRITE = "repository:write"
    REPOSITORY_DELETE = "repository:delete"
    ISSUES_WRITE = "issues:write"
    PULL_REQUESTS_WRITE = "pull_requests:write"
    PULL_REQUESTS_MERGE = "pull_requests:merge"
    COMMENTS_WRITE = "comments:write"
    REVIEWS_WRITE = "reviews:write"
    RELEASES_WRITE = "releases:write"


class PersonalAccessTokenCreate(GitEdgeBaseModel):
    """User-specified token name, expiry, repository selection, and operations."""

    name: str = Field(min_length=1, max_length=120)
    scopes: list[TokenScope] = Field(min_length=1, max_length=len(TokenScope))
    repository_ids: list[uuid.UUID] = Field(min_length=1, max_length=1000)
    expires_at: AwareDatetime | None = None

    @field_validator("name")
    @classmethod
    def nonblank_name(cls, value: str) -> str:
        """Reject blank names after trimming whitespace."""
        if not value.strip():
            raise ValueError("Token name must not be blank")
        return value.strip()

    @field_validator("scopes")
    @classmethod
    def unique_scopes(cls, value: list[TokenScope]) -> list[TokenScope]:
        """Keep scope metadata deterministic."""
        return sorted(set(value))

    @field_validator("repository_ids")
    @classmethod
    def unique_repositories(cls, value: list[uuid.UUID]) -> list[uuid.UUID]:
        """Store each explicitly selected repository once."""
        return sorted(set(value))

    @field_validator("expires_at")
    @classmethod
    def future_expiry(cls, value: datetime | None) -> datetime | None:
        """Require an expiration in the future when present."""
        if value is not None and value <= datetime.now(UTC):
            raise ValueError("Expiration must be in the future")
        return value


class PersonalAccessTokenPublic(GitEdgeBaseModel):
    """Public metadata that never includes a token or secret hash."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_id: uuid.UUID
    name: str
    prefix: str
    key_id: str
    secret_last4: str
    scopes: list[TokenScope]
    repository_ids: list[uuid.UUID]
    created_at: datetime
    expires_at: datetime | None
    last_used_at: datetime | None
    revoked_at: datetime | None
    revoked_reason: str | None


class PersonalAccessTokenIssued(PersonalAccessTokenPublic):
    """One-time response containing the newly issued plaintext credential."""

    token: str = Field(repr=False)

    @classmethod
    def from_token(cls, metadata: PersonalAccessTokenPublic, token: str) -> Self:
        """Combine safe metadata with the credential only for issuance."""
        return cls(**metadata.model_dump(), token=token)


class PersonalAccessTokenRevoke(GitEdgeBaseModel):
    """Optional audit reason when revoking a credential."""

    reason: str | None = Field(default=None, max_length=200)


class TokenRepositoryOption(GitEdgeBaseModel):
    """A repository the account can select for a token."""

    id: uuid.UUID
    name: str
    owner: str
