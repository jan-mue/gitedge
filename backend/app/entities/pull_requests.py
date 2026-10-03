"""Pull request entity model."""

import uuid

from sqlalchemy import UUID, Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.entities.issues import Issue


class PullRequest(Issue):
    """Pull request database model - extends Issue (joined table inheritance)."""

    __tablename__ = "pull_request"
    __mapper_args__ = {"polymorphic_identity": "pull_request"}

    # Use the same id as Issue (foreign key to Issue primary key) - override parent
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("issue.id"),
        primary_key=True,
    )

    head_repo_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("repository.id"), nullable=False)
    base_repo_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("repository.id"), nullable=False)
    head_branch: Mapped[str] = mapped_column(String(255), nullable=False)
    base_branch: Mapped[str] = mapped_column(String(255), nullable=False, default="main")
    merge_base: Mapped[str | None] = mapped_column(String(40), nullable=True)
    merged_commit_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    has_merged: Mapped[bool] = mapped_column(Boolean, default=False)
    merger_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=True)
