"""Service for repository issues."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from fastapi import HTTPException
from sqlalchemy import func as sa_func
from sqlalchemy import select

from app.entities.issues import Issue
from app.schemas.repositories import IssueCreate, IssuePublic, IssuesListPublic, IssueUpdate
from app.services.repositories import ensure_repository, normalize_repo_path

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.clients.repositories import RepositoryRepository
    from app.entities.users import User


class IssueService:
    """Service for managing repository issues."""

    def __init__(self, session: Session, repository_store: RepositoryRepository) -> None:
        """Initialize the issue service.

        Args:
            session: Database session.
            repository_store: Repository store.
        """
        self.session = session
        self.repository_store = repository_store

    def list_issues(self, path: str, state: str) -> IssuesListPublic:
        """List issues for a repository.

        Args:
            path: Repository path.
            state: Filter by state (open, closed, all).

        Returns:
            IssuesListPublic with the issues and counts.
        """
        repo_path = normalize_repo_path(path)
        repository = self.repository_store.get_by_path(repo_path)
        if repository is None:
            return IssuesListPublic(data=[], count=0, open_count=0, closed_count=0)

        stmt = select(Issue).where(Issue.repo_id == repository.id)
        if state in ("open", "closed"):
            stmt = stmt.where(Issue.state == state)
        stmt = stmt.order_by(Issue.number.desc())

        issues = list(self.session.execute(stmt).scalars().all())

        open_count = self.session.execute(
            select(sa_func.count()).select_from(Issue).where(Issue.repo_id == repository.id, Issue.state == "open")
        ).scalar_one()
        closed_count = self.session.execute(
            select(sa_func.count()).select_from(Issue).where(Issue.repo_id == repository.id, Issue.state == "closed")
        ).scalar_one()

        return IssuesListPublic(
            data=[self._to_public(issue, repo_path) for issue in issues],
            count=len(issues),
            open_count=open_count,
            closed_count=closed_count,
        )

    def create_issue(self, path: str, body: IssueCreate, current_user: User) -> IssuePublic:
        """Create a new issue.

        Args:
            path: Repository path.
            body: Issue creation data.
            current_user: The authenticated user.

        Returns:
            The created issue.
        """
        repo_path = normalize_repo_path(path)
        repository = ensure_repository(self.repository_store, repo_path, current_user)

        max_number = self.session.execute(
            select(sa_func.max(Issue.number)).where(Issue.repo_id == repository.id)
        ).scalar_one()
        next_number = (max_number or 0) + 1

        issue = Issue(
            repo_id=repository.id,
            number=next_number,
            title=body.title,
            body=body.body,
            state="open",
            author_email=current_user.email,
        )
        self.session.add(issue)
        self.session.commit()
        self.session.refresh(issue)

        return self._to_public(issue, repo_path)

    def get_issue(self, path: str, number: int) -> IssuePublic:
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
        issue = self._find_issue(repo_path, number)
        return self._to_public(issue, repo_path)

    def update_issue(self, path: str, number: int, body: IssueUpdate) -> IssuePublic:
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
        issue = self._find_issue(repo_path, number)

        if body.title is not None:
            issue.title = body.title
        if body.body is not None:
            issue.body = body.body
        if body.state is not None:
            if body.state not in ("open", "closed"):
                raise HTTPException(status_code=400, detail="State must be 'open' or 'closed'")
            issue.state = body.state

        issue.updated_at = datetime.now(UTC)
        self.session.commit()
        self.session.refresh(issue)

        return self._to_public(issue, repo_path)

    def _find_issue(self, repo_path: str, number: int) -> Issue:
        """Find an issue by repository path and number.

        Args:
            repo_path: Normalized repository path.
            number: Issue number.

        Returns:
            The issue entity.

        Raises:
            HTTPException: If the repository or issue is not found.
        """
        repository = self.repository_store.get_by_path(repo_path)
        if repository is None:
            raise HTTPException(status_code=404, detail="Issue not found")

        issue = self.session.execute(
            select(Issue).where(Issue.repo_id == repository.id, Issue.number == number)
        ).scalar_one_or_none()
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
