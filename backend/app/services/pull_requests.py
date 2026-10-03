"""Service for repository pull requests."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from fastapi import HTTPException
from sqlalchemy import func as sa_func
from sqlalchemy import select

from app.entities.pull_requests import PullRequest
from app.schemas.repositories import (
    PullRequestCreate,
    PullRequestPublic,
    PullRequestsListPublic,
    PullRequestUpdate,
)
from app.services.repositories import ensure_repository, normalize_repo_path

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.clients.repositories import RepositoryRepository
    from app.entities.users import User


class PullRequestService:
    """Service for managing repository pull requests."""

    def __init__(self, session: Session, repository_store: RepositoryRepository) -> None:
        """Initialize the pull request service.

        Args:
            session: Database session.
            repository_store: Repository store.
        """
        self.session = session
        self.repository_store = repository_store

    def list_pull_requests(self, path: str, state: str) -> PullRequestsListPublic:
        """List pull requests for a repository.

        Args:
            path: Repository path.
            state: Filter by state (open, closed, merged, all).

        Returns:
            PullRequestsListPublic with the pull requests and counts.
        """
        repo_path = normalize_repo_path(path)
        repository = self.repository_store.get_by_path(repo_path)
        if repository is None:
            return PullRequestsListPublic(data=[], count=0, open_count=0, closed_count=0)

        stmt = select(PullRequest).where(PullRequest.repo_id == repository.id)
        if state in ("open", "closed", "merged"):
            stmt = stmt.where(PullRequest.state == state)
        stmt = stmt.order_by(PullRequest.number.desc())

        pull_requests = list(self.session.execute(stmt).scalars().all())

        open_count = self.session.execute(
            select(sa_func.count())
            .select_from(PullRequest)
            .where(PullRequest.repo_id == repository.id, PullRequest.state == "open")
        ).scalar_one()
        closed_count = self.session.execute(
            select(sa_func.count())
            .select_from(PullRequest)
            .where(PullRequest.repo_id == repository.id, PullRequest.state.in_(["closed", "merged"]))
        ).scalar_one()

        return PullRequestsListPublic(
            data=[self._to_public(pr, repo_path) for pr in pull_requests],
            count=len(pull_requests),
            open_count=open_count,
            closed_count=closed_count,
        )

    def create_pull_request(self, path: str, body: PullRequestCreate, current_user: User) -> PullRequestPublic:
        """Create a new pull request.

        Args:
            path: Repository path.
            body: Pull request creation data.
            current_user: The authenticated user.

        Returns:
            The created pull request.
        """
        repo_path = normalize_repo_path(path)
        repository = ensure_repository(self.repository_store, repo_path, current_user)

        max_number = self.session.execute(
            select(sa_func.max(PullRequest.number)).where(PullRequest.repo_id == repository.id)
        ).scalar_one()
        next_number = (max_number or 0) + 1

        pull_request = PullRequest(
            repo_id=repository.id,
            number=next_number,
            title=body.title,
            body=body.body,
            state="open",
            author_email=current_user.email,
            head_repo_id=repository.id,
            base_repo_id=repository.id,
            head_branch=body.head_branch,
            base_branch=body.base_branch,
        )
        self.session.add(pull_request)
        self.session.commit()
        self.session.refresh(pull_request)

        return self._to_public(pull_request, repo_path)

    def get_pull_request(self, path: str, number: int) -> PullRequestPublic:
        """Get a single pull request by number.

        Args:
            path: Repository path.
            number: Pull request number.

        Returns:
            The pull request.

        Raises:
            HTTPException: If the pull request is not found.
        """
        repo_path = normalize_repo_path(path)
        pull_request = self._find_pull_request(repo_path, number)
        return self._to_public(pull_request, repo_path)

    def update_pull_request(self, path: str, number: int, body: PullRequestUpdate) -> PullRequestPublic:
        """Update a pull request.

        Args:
            path: Repository path.
            number: Pull request number.
            body: Fields to update.

        Returns:
            The updated pull request.

        Raises:
            HTTPException: If the pull request is not found or the state is invalid.
        """
        repo_path = normalize_repo_path(path)
        pull_request = self._find_pull_request(repo_path, number)

        if body.title is not None:
            pull_request.title = body.title
        if body.body is not None:
            pull_request.body = body.body
        if body.state is not None:
            if body.state not in ("open", "closed", "merged"):
                raise HTTPException(status_code=400, detail="State must be 'open', 'closed', or 'merged'")
            pull_request.state = body.state

        pull_request.updated_at = datetime.now(UTC)
        self.session.commit()
        self.session.refresh(pull_request)

        return self._to_public(pull_request, repo_path)

    def _find_pull_request(self, repo_path: str, number: int) -> PullRequest:
        """Find a pull request by repository path and number.

        Args:
            repo_path: Normalized repository path.
            number: Pull request number.

        Returns:
            The pull request entity.

        Raises:
            HTTPException: If the repository or pull request is not found.
        """
        repository = self.repository_store.get_by_path(repo_path)
        if repository is None:
            raise HTTPException(status_code=404, detail="Pull request not found")

        pull_request = self.session.execute(
            select(PullRequest).where(PullRequest.repo_id == repository.id, PullRequest.number == number)
        ).scalar_one_or_none()
        if pull_request is None:
            raise HTTPException(status_code=404, detail="Pull request not found")
        return pull_request

    @staticmethod
    def _to_public(pr: PullRequest, repo_path: str) -> PullRequestPublic:
        """Convert a pull request entity to its public representation.

        Args:
            pr: The pull request entity.
            repo_path: The repository path.

        Returns:
            The public pull request representation.
        """
        return PullRequestPublic(
            id=pr.id,
            repo_path=repo_path,
            number=pr.number,
            title=pr.title,
            body=pr.body,
            state=pr.state,
            head_branch=pr.head_branch,
            base_branch=pr.base_branch,
            author_email=pr.author_email,
            merge_base=pr.merge_base,
            merged_commit_id=pr.merged_commit_id,
            has_merged=pr.has_merged,
            created_at=pr.created_at,
            updated_at=pr.updated_at,
        )
