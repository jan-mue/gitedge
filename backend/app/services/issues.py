"""Service for repository issues."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from fastapi import HTTPException

from app.entities.issues import Issue
from app.schemas.repositories import IssueCreate, IssuePublic, IssuesListPublic, IssueUpdate
from app.services.repositories import ensure_repository, normalize_repo_path

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
        activity_service: ActivityService | None = None,
    ) -> None:
        """Initialize the issue service.

        Args:
            issue_store: Issue store.
            repository_store: Repository store.
            activity_service: Optional service used to record activity.
        """
        self.issue_store = issue_store
        self.repository_store = repository_store
        self.activity_service = activity_service

    async def list_issues(self, path: str, state: str) -> IssuesListPublic:
        """List issues for a repository.

        Args:
            path: Repository path.
            state: Filter by state (open, closed, all).

        Returns:
            IssuesListPublic with the issues and counts.
        """
        repo_path = normalize_repo_path(path)
        repository = await self.repository_store.get_by_path(repo_path)
        if repository is None:
            return IssuesListPublic(data=[], count=0, open_count=0, closed_count=0)

        filter_state = state if state in ("open", "closed") else None
        issues = await self.issue_store.list_by_repo(repository.id, filter_state)

        return IssuesListPublic(
            data=[self._to_public(issue, repo_path) for issue in issues],
            count=len(issues),
            open_count=await self.issue_store.count_by_state(repository.id, "open"),
            closed_count=await self.issue_store.count_by_state(repository.id, "closed"),
        )

    async def create_issue(self, path: str, body: IssueCreate, current_user: User) -> IssuePublic:
        """Create a new issue.

        Args:
            path: Repository path.
            body: Issue creation data.
            current_user: The authenticated user.

        Returns:
            The created issue.
        """
        repo_path = normalize_repo_path(path)
        repository = await ensure_repository(self.repository_store, repo_path, current_user)

        issue = Issue(
            repo_id=repository.id,
            number=await self.issue_store.next_number(repository.id),
            title=body.title,
            body=body.body,
            state="open",
            author_email=current_user.email,
        )
        await self.issue_store.add(issue)

        if self.activity_service is not None:
            await self.activity_service.record(
                actor=current_user,
                repo=repository,
                kind="issue_open",
                title=issue.title,
                target_type="issue",
                target_number=issue.number,
            )

        return self._to_public(issue, repo_path)

    async def get_issue(self, path: str, number: int) -> IssuePublic:
        """Get a single issue by number.

        Args:
            path: Repository path.
            number: Issue number.

        Returns:
            The issue.

        Raises:
            HTTPException: If the issue is not found.
        """
        repo_path = normalize_repo_path(path)
        issue = await self._find_issue(repo_path, number)
        return self._to_public(issue, repo_path)

    async def update_issue(self, path: str, number: int, body: IssueUpdate) -> IssuePublic:
        """Update an issue.

        Args:
            path: Repository path.
            number: Issue number.
            body: Fields to update.

        Returns:
            The updated issue.

        Raises:
            HTTPException: If the issue is not found or the state is invalid.
        """
        repo_path = normalize_repo_path(path)
        issue = await self._find_issue(repo_path, number)

        if body.title is not None:
            issue.title = body.title
        if body.body is not None:
            issue.body = body.body
        if body.state is not None:
            if body.state not in ("open", "closed"):
                raise HTTPException(status_code=400, detail="State must be 'open' or 'closed'")
            issue.state = body.state

        issue.updated_at = datetime.now(UTC)
        await self.issue_store.update(issue)

        if self.activity_service is not None and body.state is not None:
            kind = "issue_close" if body.state == "closed" else "issue_reopen"
            repository = await self.repository_store.get_by_path(repo_path)
            await self.activity_service.record(
                actor=None,
                repo=repository,
                kind=kind,
                title=issue.title,
                target_type="issue",
                target_number=issue.number,
            )

        return self._to_public(issue, repo_path)

    async def _find_issue(self, repo_path: str, number: int) -> Issue:
        """Find an issue by repository path and number.

        Args:
            repo_path: Normalized repository path.
            number: Issue number.

        Returns:
            The issue entity.

        Raises:
            HTTPException: If the repository or issue is not found.
        """
        repository = await self.repository_store.get_by_path(repo_path)
        if repository is None:
            raise HTTPException(status_code=404, detail="Issue not found")

        issue = await self.issue_store.get_by_number(repository.id, number)
        if issue is None:
            raise HTTPException(status_code=404, detail="Issue not found")
        return issue

    @staticmethod
    def _to_public(issue: Issue, repo_path: str) -> IssuePublic:
        """Convert an issue entity to its public representation.

        Args:
            issue: The issue entity.
            repo_path: The repository path.

        Returns:
            The public issue representation.
        """
        return IssuePublic(
            id=issue.id,
            repo_path=repo_path,
            number=issue.number,
            title=issue.title,
            body=issue.body,
            state=issue.state,
            author_email=issue.author_email,
            created_at=issue.created_at,
            updated_at=issue.updated_at,
        )
