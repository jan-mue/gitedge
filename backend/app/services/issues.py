"""Service for repository issues."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from fastapi import HTTPException

from app.entities.activity import ActivityKind, ActivityTargetType
from app.entities.issues import Issue, IssueState
from app.schemas.repositories import IssueCreate, IssuePublic, IssuesListPublic, IssueUpdate
from app.services.repositories import ensure_repository

if TYPE_CHECKING:
    from app.clients.issues import IssueStore
    from app.clients.repositories import RepositoryStore
    from app.entities.users import User
    from app.services.activity import ActivityService


class IssueService:
    """Service for managing repository issues."""

    def __init__(
        self,
        issue_store: IssueStore,
        repository_store: RepositoryStore,
        activity_service: ActivityService,
    ) -> None:
        """Initialize the issue service.

        Args:
            issue_store: Issue store.
            repository_store: Repository store.
            activity_service: Service used to record activity.
        """
        self.issue_store = issue_store
        self.repository_store = repository_store
        self.activity_service = activity_service

    async def list_issues(self, owner: str, name: str, state: str) -> IssuesListPublic:
        """List issues for a repository.

        Args:
            owner: Owner name.
            name: Repository name.
            state: Filter by state (open, closed, all).

        Returns:
            IssuesListPublic with the issues and counts.
        """
        repository = await self.repository_store.find_by_owner_and_name(owner, name)
        if repository is None:
            return IssuesListPublic(data=[], count=0, open_count=0, closed_count=0)

        filter_state = IssueState(state) if state in (IssueState.OPEN, IssueState.CLOSED) else None
        issues = await self.issue_store.list_by_repo(repository.id, filter_state)

        return IssuesListPublic(
            data=[self._to_public(issue, owner, name) for issue in issues],
            count=len(issues),
            open_count=await self.issue_store.count_by_state(repository.id, IssueState.OPEN),
            closed_count=await self.issue_store.count_by_state(repository.id, IssueState.CLOSED),
        )

    async def create_issue(self, owner: str, name: str, body: IssueCreate, current_user: User) -> IssuePublic:
        """Create a new issue.

        Args:
            owner: Owner name.
            name: Repository name.
            body: Issue creation data.
            current_user: The authenticated user.

        Returns:
            The created issue.
        """
        repository = await ensure_repository(self.repository_store, owner, name)

        issue = Issue(
            repo_id=repository.id,
            number=await self.issue_store.next_number(repository.id),
            title=body.title,
            body=body.body,
            state=IssueState.OPEN,
            author_id=current_user.id,
        )
        await self.issue_store.add(issue)
        issue.author = current_user

        await self.activity_service.record(
            actor=current_user,
            repo=repository,
            kind=ActivityKind.ISSUE_OPEN,
            title=issue.title,
            target_type=ActivityTargetType.ISSUE,
            target_number=issue.number,
        )

        return self._to_public(issue, owner, name)

    async def get_issue(self, owner: str, name: str, number: int) -> IssuePublic:
        """Get a single issue by number.

        Args:
            owner: Owner name.
            name: Repository name.
            number: Issue number.

        Returns:
            The issue.

        Raises:
            HTTPException: If the issue is not found.
        """
        issue = await self._find_issue(owner, name, number)
        return self._to_public(issue, owner, name)

    async def update_issue(
        self, owner: str, name: str, number: int, body: IssueUpdate, current_user: User
    ) -> IssuePublic:
        """Update an issue.

        Args:
            owner: Owner name.
            name: Repository name.
            number: Issue number.
            body: Fields to update.
            current_user: The authenticated user.

        Returns:
            The updated issue.

        Raises:
            HTTPException: If the issue is not found or the state is invalid.
        """
        issue = await self._find_issue(owner, name, number)

        if body.title is not None:
            issue.title = body.title
        if body.body is not None:
            issue.body = body.body
        if body.state is not None:
            if body.state not in (IssueState.OPEN, IssueState.CLOSED):
                raise HTTPException(status_code=400, detail="State must be 'open' or 'closed'")
            issue.state = body.state

        issue.updated_at = datetime.now(UTC)
        await self.issue_store.update(issue)

        if body.state is not None:
            kind = ActivityKind.ISSUE_CLOSE if body.state == IssueState.CLOSED else ActivityKind.ISSUE_REOPEN
            repository = await self.repository_store.get_by_owner_and_name(owner, name)
            await self.activity_service.record(
                actor=current_user,
                repo=repository,
                kind=kind,
                title=issue.title,
                target_type=ActivityTargetType.ISSUE,
                target_number=issue.number,
            )

        return self._to_public(issue, owner, name)

    async def _find_issue(self, owner: str, name: str, number: int) -> Issue:
        """Find an issue by repository and number.

        Args:
            owner: Owner name.
            name: Repository name.
            number: Issue number.

        Returns:
            The issue entity.

        Raises:
            IssueNotFoundError: If the repository or issue is not found.
        """
        repository = await self.repository_store.get_by_owner_and_name(owner, name)
        return await self.issue_store.get_by_number(repository.id, number)

    @staticmethod
    def _to_public(issue: Issue, owner: str, name: str) -> IssuePublic:
        """Convert an issue entity to its public representation.

        Args:
            issue: The issue entity (with its author loaded).
            owner: Owner name.
            name: Repository name.

        Returns:
            The public issue representation.
        """
        return IssuePublic(
            id=issue.id,
            repo_owner=owner,
            repo_name=name,
            number=issue.number,
            title=issue.title,
            body=issue.body,
            state=issue.state,
            author_username=issue.author.name,
            created_at=issue.created_at,
            updated_at=issue.updated_at,
        )
