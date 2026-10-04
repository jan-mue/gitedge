"""Service for issue and pull request comments."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException

from app.entities.comments import Comment
from app.schemas.comments import CommentCreate, CommentPublic, CommentsPublic
from app.services.repositories import normalize_repo_path

if TYPE_CHECKING:
    import uuid

    from app.clients.comments import CommentStore
    from app.clients.issues import IssueStore
    from app.clients.pull_requests import PullRequestStore
    from app.clients.repositories import RepositoryStore
    from app.clients.users import UserStore
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
        user_store: UserStore,
        activity_service: ActivityService,
    ) -> None:
        """Initialize the comment service.

        Args:
            comment_store: Comment store.
            issue_store: Issue store.
            pull_request_store: Pull request store.
            repository_store: Repository store.
            user_store: User store.
            activity_service: Service used to record activity.
        """
        self.comment_store = comment_store
        self.issue_store = issue_store
        self.pull_request_store = pull_request_store
        self.repository_store = repository_store
        self.user_store = user_store
        self.activity_service = activity_service

    async def list_comments(self, path: str, number: int) -> CommentsPublic:
        """List comments for an issue or pull request.

        Args:
            path: Repository path.
            number: Issue or pull request number.

        Returns:
            CommentsPublic with the comments, oldest first.

        Raises:
            HTTPException: If the issue or pull request is not found.
        """
        repo_path = normalize_repo_path(path)
        issue = await self._find_issue(repo_path, number)
        comments = await self.comment_store.list_by_issue(issue.id)
        return CommentsPublic(data=await self._to_public_list(comments, issue, repo_path), count=len(comments))

    async def create_comment(self, path: str, number: int, body: CommentCreate, current_user: User) -> CommentPublic:
        """Create a comment on an issue or pull request.

        Args:
            path: Repository path.
            number: Issue or pull request number.
            body: Comment creation data.
            current_user: The authenticated user.

        Returns:
            The created comment.

        Raises:
            HTTPException: If the issue or pull request is not found.
        """
        repo_path = normalize_repo_path(path)
        issue = await self._find_issue(repo_path, number)

        comment = Comment(
            issue_id=issue.id,
            author_id=current_user.id,
            author_email=current_user.email,
            body=body.body,
        )
        await self.comment_store.add(comment)

        repository = await self.repository_store.get_by_path(repo_path)
        if repository is not None:
            await self.activity_service.record(
                actor=current_user,
                repo=repository,
                kind="comment",
                title=issue.title,
                target_type=issue.kind,
                target_number=issue.number,
            )

        return await self._to_public(comment, issue, repo_path)

    async def _find_issue(self, repo_path: str, number: int) -> Issue:
        """Find an issue or pull request by repository path and number.

        Args:
            repo_path: Normalized repository path.
            number: Issue or pull request number.

        Returns:
            The issue or pull request entity.

        Raises:
            HTTPException: If the repository, issue or pull request is not found.
        """
        repository = await self.repository_store.get_by_path(repo_path)
        if repository is None:
            raise HTTPException(status_code=404, detail="Issue not found")

        issue = await self.issue_store.get_by_number(repository.id, number)
        if issue is None:
            issue = await self.pull_request_store.get_by_number(repository.id, number)
        if issue is None:
            raise HTTPException(status_code=404, detail="Issue not found")
        return issue

    async def _to_public_list(self, comments: list[Comment], issue: Issue, repo_path: str) -> list[CommentPublic]:
        """Convert comment entities to their public representation.

        Args:
            comments: The comment entities.
            issue: The issue or pull request the comments belong to.
            repo_path: The repository path.

        Returns:
            The public comment representations.
        """
        usernames: dict[uuid.UUID, str] = {}
        for comment in comments:
            if comment.author_id is not None and comment.author_id not in usernames:
                user = await self.user_store.get(comment.author_id)
                if user is not None and user.username:
                    usernames[comment.author_id] = user.username
        return [self._to_public_sync(comment, issue, repo_path, usernames) for comment in comments]

    async def _to_public(self, comment: Comment, issue: Issue, repo_path: str) -> CommentPublic:
        """Convert a single comment entity to its public representation.

        Args:
            comment: The comment entity.
            issue: The issue or pull request the comment belongs to.
            repo_path: The repository path.

        Returns:
            The public comment representation.
        """
        username = None
        if comment.author_id is not None:
            user = await self.user_store.get(comment.author_id)
            if user is not None:
                username = user.username
        usernames: dict[uuid.UUID, str] = {}
        if comment.author_id is not None and username is not None:
            usernames[comment.author_id] = username
        return self._to_public_sync(comment, issue, repo_path, usernames)

    @staticmethod
    def _to_public_sync(
        comment: Comment, issue: Issue, repo_path: str, usernames: dict[uuid.UUID, str]
    ) -> CommentPublic:
        """Build a public comment representation from an entity and username map."""
        return CommentPublic(
            id=comment.id,
            repo_path=repo_path,
            issue_number=issue.number,
            author_email=comment.author_email,
            author_username=usernames.get(comment.author_id) if comment.author_id else None,
            body=comment.body,
            created_at=comment.created_at,
            updated_at=comment.updated_at,
        )
