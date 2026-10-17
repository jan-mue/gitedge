"""Pull request review and per-user workspace schemas."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field

from app.entities.reviews import ReviewState
from app.schemas.base import GitEdgeBaseModel
from app.schemas.repositories import DiffHunk


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


class ReviewCommentPublic(ReviewLineComment):
    """A submitted line comment with a bounded, backend-highlighted snapshot."""

    id: uuid.UUID | None = None
    body_html: str = ""
    context: DiffHunk | None = None


class ReviewReplyCreate(GitEdgeBaseModel):
    """Reply to an individual line comment, or to the overall review body."""

    reply_to: uuid.UUID | None = None
    comment_index: int | None = Field(default=None, ge=0)
    body: str = Field(min_length=1, max_length=20000)


class ReviewReplyPublic(ReviewReplyCreate):
    """A published reply with server-rendered Markdown."""

    id: uuid.UUID
    author_username: str
    created_at: datetime
    body_html: str


class ReviewPublic(GitEdgeBaseModel):
    """An immutable submitted review."""

    id: uuid.UUID
    author_username: str
    created_at: datetime
    state: ReviewState
    body: str = ""
    body_html: str = ""
    summary_comment_id: uuid.UUID | None = None
    base_commit: str
    head_commit: str
    comments: list[ReviewCommentPublic] = Field(default_factory=list)
    replies: list[ReviewReplyPublic] = Field(default_factory=list)
    outdated: bool | None = None


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
