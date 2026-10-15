"""Pull request review and per-user workspace schemas."""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field

from app.schemas.base import GitEdgeBaseModel


class ReviewState(StrEnum):
    """The outcome of a submitted review."""

    APPROVED = "approved"
    COMMENT = "comment"
    CHANGES_REQUESTED = "changes_requested"


class ReviewLineComment(GitEdgeBaseModel):
    """A review comment anchored to a side and line of a compared file."""

    path: str = Field(min_length=1, max_length=4096)
    side: Literal["old", "new"]
    line: int = Field(ge=1)
    body: str = Field(min_length=1, max_length=20000)


class ReviewDraft(GitEdgeBaseModel):
    """The exact comparison and comments being reviewed."""

    base_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    head_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    body: str = Field(default="", max_length=20000)
    comments: list[ReviewLineComment] = Field(default_factory=list, max_length=500)


class ReviewSubmit(ReviewDraft):
    """A review submitted with an outcome and optional overall comment."""

    state: ReviewState


class ReviewPublic(ReviewSubmit):
    """An immutable submitted review."""

    id: uuid.UUID
    author_username: str
    created_at: datetime


class ReviewedFileUpdate(GitEdgeBaseModel):
    """Mark a file viewed at an exact comparison."""

    base_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    head_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    path: str = Field(min_length=1, max_length=4096)
    reviewed: bool


class ReviewWorkspacePublic(GitEdgeBaseModel):
    """A user's private draft and viewed files for the current comparison."""

    draft: ReviewDraft | None = None
    reviewed_paths: list[str] = Field(default_factory=list)
