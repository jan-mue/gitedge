"""Service for issue and pull request comments."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from fastapi import HTTPException

from app.entities.activity import ActivityKind, ActivityTargetType
from app.entities.comments import Comment
from app.exceptions import IssueNotFoundError, PullRequestNotFoundError
from app.schemas.comments import CommentCreate, CommentPublic, CommentsPublic, CommentUpdate
from app.services.markdown import render_markdown

if TYPE_CHECKING:
    import uuid

    from app.clients.comments import CommentStore
    from app.clients.issues import IssueStore
    from app.clients.pull_requests import PullRequestStore
    from app.clients.repositories import RepositoryStore
    from app.entities.issues import Issue
    from app.entities.users import User
    from app.services.activity import ActivityService


class CommentService:
    """Service for commenting on issues and pull requests."""

    def __init__(
        self,
        *,
        comment_store: CommentStore,
        issue_store: IssueStore,
        pull_request_store: PullRequestStore,
        repository_store: RepositoryStore,
        activity_service: ActivityService,
    ) -> None:
        """Initialize the comment service.

        Args:
            comment_store: Comment store.
            issue_store: Issue store.
            pull_request_store: Pull request store.
            repository_store: Repository store.
            activity_service: Service used to record activity.
        """
        self.comment_store = comment_store
        self.issue_store = issue_store
        self.pull_request_store = pull_request_store
        self.repository_store = repository_store
        self.activity_service = activity_service

    async def list_comments(self, owner: str, name: str, number: int) -> CommentsPublic:
        """List comments for an issue or pull request.

        Args:
            owner: Owner name.
            name: Repository name.
            number: Issue or pull request number.

        Returns:
            CommentsPublic with the comments, oldest first.

        Raises:
            HTTPException: If the issue or pull request is not found.
        """
        issue = await self._find_issue(owner, name, number)
        comments = issue.comments
        return CommentsPublic(data=[self._to_public(comment) for comment in comments], count=len(comments))

    async def create_comment(
        self, owner: str, name: str, number: int, body: CommentCreate, current_user: User
    ) -> CommentPublic:
        """Create a comment on an issue or pull request.

        Args:
            owner: Owner name.
            name: Repository name.
            number: Issue or pull request number.
            body: Comment creation data.
            current_user: The authenticated user.

        Returns:
            The created comment.

        Raises:
            HTTPException: If the issue or pull request is not found.
        """
        issue = await self._find_issue(owner, name, number)

        comment = Comment(issue_id=issue.id, author_id=current_user.id, body=body.body)
        await self.comment_store.add(comment)
        comment.author = current_user

        repository = await self.repository_store.get_by_owner_and_name(owner, name)
        await self.activity_service.record(
            actor=current_user,
            repo=repository,
            kind=ActivityKind.COMMENT,
            title=issue.title,
            target_type=ActivityTargetType(issue.kind),
            target_number=issue.number,
        )

        return self._to_public(comment)

    async def update_comment(self, comment_id: uuid.UUID, body: CommentUpdate, current_user: User) -> CommentPublic:
        """Update a comment's body.

        Args:
            comment_id: The comment id.
            body: Comment update data.
            current_user: The authenticated user.

        Returns:
            The updated comment.

        Raises:
            NotFoundError: If the comment is not found.
            HTTPException: If the user is not allowed to edit the comment.
        """
        comment = await self.comment_store.get(comment_id)
        if comment.author_id != current_user.id and not current_user.is_superuser:
            raise HTTPException(status_code=403, detail="You can only edit your own comments")

        comment.body = body.body
        comment.updated_at = datetime.now(UTC)
        await self.comment_store.update(comment)
        return self._to_public(comment)

    async def delete_comment(self, comment_id: uuid.UUID, current_user: User) -> None:
        """Delete a comment.

        Args:
            comment_id: The comment id.
            current_user: The authenticated user.

        Raises:
            NotFoundError: If the comment is not found.
            HTTPException: If the user is not allowed to delete the comment.
        """
        comment = await self.comment_store.get(comment_id)
        if comment.author_id != current_user.id and not current_user.is_superuser:
            raise HTTPException(status_code=403, detail="You can only delete your own comments")

        await self.comment_store.delete(comment)

    async def _find_issue(self, owner: str, name: str, number: int) -> Issue:
        """Find an issue or pull request by repository and number.

        Args:
            owner: Owner name.
            name: Repository name.
            number: Issue or pull request number.

        Returns:
            The issue or pull request entity.

        Raises:
            IssueNotFoundError: If the repository, issue or pull request is not found.
        """
        repository = await self.repository_store.get_by_owner_and_name(owner, name)
        try:
            return await self.issue_store.get_by_number(repository.id, number)
        except IssueNotFoundError:
            pass
        try:
            return await self.pull_request_store.get_by_number(repository.id, number)
        except PullRequestNotFoundError as exc:
            raise IssueNotFoundError from exc

    @staticmethod
    def _to_public(comment: Comment) -> CommentPublic:
        """Build a public comment representation from a comment entity."""
        return CommentPublic(
            id=comment.id,
            author_username=comment.author.name,
            body=comment.body,
            body_html=render_markdown(comment.body),
            created_at=comment.created_at,
            updated_at=comment.updated_at,
        )
