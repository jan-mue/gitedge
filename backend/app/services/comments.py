"""Service for issue and pull request comments."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from app.entities.activity import ActivityKind, ActivityTargetType
from app.entities.comments import Comment
from app.exceptions import (
    CommentNotFoundError,
    IssueNotFoundError,
    PullRequestNotFoundError,
)
from app.schemas.comments import (
    CommentCreate,
    CommentPublic,
    CommentsPublic,
    CommentUpdate,
    ReactionPublic,
    ReactionsPublic,
)
from app.utils.markdown import render_markdown

if TYPE_CHECKING:
    import uuid

    from app.clients.comments import CommentStore
    from app.clients.issues import IssueStore
    from app.clients.pull_requests import PullRequestStore
    from app.clients.repositories import RepositoryStore
    from app.entities.issues import Issue
    from app.entities.repositories import Repository
    from app.entities.users import User
    from app.services.activity import ActivityService
    from app.services.authorization import AuthorizationService


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
        authorization: AuthorizationService,
    ) -> None:
        """Initialize the comment service.

        Args:
            authorization: Authorization service for scoped role checks.
            comment_store: Comment store.
            issue_store: Issue store.
            pull_request_store: Pull request store.
            repository_store: Repository store.
            activity_service: Service used to record activity.
        """
        self.authorization = authorization
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
            ApplicationError: If the issue or pull request is not found.
        """
        issue = await self._find_issue(owner, name, number)
        comments = await self.comment_store.list_by_issue(issue.id)
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
            ApplicationError: If the issue or pull request is not found.
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
            comment_id=comment.id,
            text=comment.body,
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
            ApplicationError: If the user is not allowed to edit the comment.
        """
        comment = await self.comment_store.get(comment_id)
        repository = await self.repository_store.get(comment.issue.repo_id)
        await self.authorization.require(repository, current_user, "comments:write")
        if comment.author_id != current_user.id:
            await self.authorization.require(repository, current_user, "comments:moderate")

        previous_body = comment.body
        comment.body = body.body
        comment.updated_at = datetime.now(UTC)
        await self.comment_store.update(comment)
        if comment.body != previous_body:
            issue, repository = await self.comment_store.context(comment)
            await self.activity_service.record(
                actor=current_user,
                repo=repository,
                kind=ActivityKind.COMMENT_EDIT,
                title=issue.title,
                target_type=ActivityTargetType(issue.kind),
                target_number=issue.number,
                comment_id=comment.id,
                text=comment.body,
                previous_text=previous_body,
            )
        return self._to_public(comment)

    async def delete_comment(self, comment_id: uuid.UUID, current_user: User) -> None:
        """Delete a comment.

        Args:
            comment_id: The comment id.
            current_user: The authenticated user.

        Raises:
            NotFoundError: If the comment is not found.
            ApplicationError: If the user is not allowed to delete the comment.
        """
        comment = await self.comment_store.get(comment_id)
        repository = await self.repository_store.get(comment.issue.repo_id)
        await self.authorization.require(repository, current_user, "comments:write")
        if comment.author_id != current_user.id:
            await self.authorization.require(repository, current_user, "comments:moderate")

        await self.comment_store.delete(comment)

    async def list_reactions(self, comment_id: uuid.UUID, current_user: User | None) -> ReactionsPublic:
        """Read reaction totals after checking the comment is accessible."""
        comment = await self.comment_store.get(comment_id)
        await self._reaction_context(comment, current_user)
        reactions = await self.comment_store.reactions(comment_id)
        emojis = list(dict.fromkeys(reaction.emoji for reaction in reactions))
        return ReactionsPublic(
            data=[
                ReactionPublic(
                    emoji=emoji,
                    count=sum(reaction.emoji == emoji for reaction in reactions),
                    reacted=current_user is not None
                    and any(reaction.emoji == emoji and reaction.user_id == current_user.id for reaction in reactions),
                )
                for emoji in emojis
            ]
        )

    async def react(self, comment_id: uuid.UUID, emoji: str, current_user: User, *, enabled: bool) -> ReactionsPublic:
        """Add or remove a reaction; only new reactions create activity."""
        comment = await self.comment_store.get(comment_id)
        issue, repository = await self._reaction_context(comment, current_user, "comments:write")
        added = await self.comment_store.set_reaction(comment_id, current_user.id, emoji, enabled=enabled)
        if added:
            await self.activity_service.record(
                actor=current_user,
                repo=repository,
                kind=ActivityKind.REACTION,
                title=f"{emoji} {issue.title}",
                target_type=ActivityTargetType(issue.kind),
                target_number=issue.number,
                comment_id=comment.id,
            )
        return await self.list_reactions(comment_id, current_user)

    async def _reaction_context(
        self, comment: Comment, user: User | None, operation: str = "repository:read"
    ) -> tuple[Issue, Repository]:
        """Protect private discussion reactions."""
        issue, repo = await self.comment_store.context(comment)
        if not await self.authorization.can(repo, user, operation):
            raise CommentNotFoundError
        return issue, repo

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
