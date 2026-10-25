"""Job-capability cache protocol contracts."""

import uuid

from pydantic import Field

from app.schemas.base import GitEdgeBaseModel


class CacheIdentity(GitEdgeBaseModel):
    """Validate protocol keys before querying or storing payloads."""

    key: str = Field(min_length=1, max_length=512)
    version: str = Field(max_length=512)


class CacheEntry(CacheIdentity):
    """Public metadata identifies an immutable payload generation."""

    id: uuid.UUID
    size: int
