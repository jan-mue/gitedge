"""Service for issue and pull request comments."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException

from app.entities.activity import ActivityKind, ActivityTargetType
from app.entities.comments import Comment
from app.schemas.comments import CommentCreate, CommentPublic, CommentsPublic

if TYPE_CHECKING:
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
        comments = await self.comment_store.list_by_issue(issue.id)
        return CommentsPublic(
            data=[self._to_public(comment, issue, owner, name) for comment in comments], count=len(comments)
        )

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
        if repository is not None:
            await self.activity_service.record(
                actor=current_user,
                repo=repository,
                kind=ActivityKind.COMMENT,
                title=issue.title,
                target_type=ActivityTargetType(issue.kind),
                target_number=issue.number,
            )

        return self._to_public(comment, issue, owner, name)

    async def _find_issue(self, owner: str, name: str, number: int) -> Issue:
        """Find an issue or pull request by repository and number.

        Args:
            owner: Owner name.
            name: Repository name.
            number: Issue or pull request number.

        Returns:
            The issue or pull request entity.

        Raises:
            HTTPException: If the repository, issue or pull request is not found.
        """
        repository = await self.repository_store.get_by_owner_and_name(owner, name)
        if repository is None:
            raise HTTPException(status_code=404, detail="Issue not found")

        issue = await self.issue_store.get_by_number(repository.id, number)
        if issue is None:
            issue = await self.pull_request_store.get_by_number(repository.id, number)
        if issue is None:
            raise HTTPException(status_code=404, detail="Issue not found")
        return issue

    @staticmethod
    def _to_public(comment: Comment, issue: Issue, owner: str, name: str) -> CommentPublic:
        """Build a public comment representation from a comment entity."""
        return CommentPublic(
            id=comment.id,
            repo_owner=owner,
            repo_name=name,
            issue_number=issue.number,
            author_username=comment.author.name if comment.author is not None else None,
            body=comment.body,
            created_at=comment.created_at,
            updated_at=comment.updated_at,
        )
