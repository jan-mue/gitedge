"""Service for repository pull requests."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from fastapi import HTTPException

from app.entities.activity import ActivityKind, ActivityTargetType
from app.entities.issues import IssueState
from app.entities.pull_requests import PullRequest
from app.schemas.repositories import (
    PullRequestCreate,
    PullRequestPublic,
    PullRequestsListPublic,
    PullRequestUpdate,
)
from app.services.repositories import ensure_repository, normalize_repo_path

if TYPE_CHECKING:
    from app.clients.pull_requests import PullRequestStore
    from app.clients.repositories import RepositoryStore
    from app.entities.users import User
    from app.services.activity import ActivityService


class PullRequestService:
    """Service for managing repository pull requests."""

    def __init__(
        self,
        pull_request_store: PullRequestStore,
        repository_store: RepositoryStore,
        activity_service: ActivityService | None = None,
    ) -> None:
        """Initialize the pull request service.

        Args:
            pull_request_store: Pull request store.
            repository_store: Repository store.
            activity_service: Optional service used to record activity.
        """
        self.pull_request_store = pull_request_store
        self.repository_store = repository_store
        self.activity_service = activity_service

    async def list_pull_requests(self, path: str, state: str) -> PullRequestsListPublic:
        """List pull requests for a repository.

        Args:
            path: Repository path.
            state: Filter by state (open, closed, merged, all).

        Returns:
            PullRequestsListPublic with the pull requests and counts.
        """
        repo_path = normalize_repo_path(path)
        repository = await self.repository_store.get_by_path(repo_path)
        if repository is None:
            return PullRequestsListPublic(data=[], count=0, open_count=0, closed_count=0)

        filter_state = IssueState(state) if state in (IssueState.OPEN, IssueState.CLOSED, IssueState.MERGED) else None
        pull_requests = await self.pull_request_store.list_by_repo(repository.id, filter_state)

        return PullRequestsListPublic(
            data=[self._to_public(pr, repo_path) for pr in pull_requests],
            count=len(pull_requests),
            open_count=await self.pull_request_store.count_by_state(repository.id, IssueState.OPEN),
            closed_count=await self.pull_request_store.count_by_states(
                repository.id, [IssueState.CLOSED, IssueState.MERGED]
            ),
        )

    async def create_pull_request(self, path: str, body: PullRequestCreate, current_user: User) -> PullRequestPublic:
        """Create a new pull request.

        Args:
            path: Repository path.
            body: Pull request creation data.
            current_user: The authenticated user.

        Returns:
            The created pull request.
        """
        repo_path = normalize_repo_path(path)
        repository = await ensure_repository(self.repository_store, repo_path, current_user)

        pull_request = PullRequest(
            repo_id=repository.id,
            number=await self.pull_request_store.next_number(repository.id),
            title=body.title,
            body=body.body,
            state=IssueState.OPEN,
            author_email=current_user.email,
            head_repo_id=repository.id,
            base_repo_id=repository.id,
            head_branch=body.head_branch,
            base_branch=body.base_branch,
        )
        await self.pull_request_store.add(pull_request)

        if self.activity_service is not None:
            await self.activity_service.record(
                actor=current_user,
                repo=repository,
                kind=ActivityKind.PULL_REQUEST_OPEN,
                title=pull_request.title,
                target_type=ActivityTargetType.PULL_REQUEST,
                target_number=pull_request.number,
            )

        return self._to_public(pull_request, repo_path)

    async def get_pull_request(self, path: str, number: int) -> PullRequestPublic:
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
        pull_request = await self._find_pull_request(repo_path, number)
        return self._to_public(pull_request, repo_path)

    async def update_pull_request(self, path: str, number: int, body: PullRequestUpdate) -> PullRequestPublic:
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
        pull_request = await self._find_pull_request(repo_path, number)

        if body.title is not None:
            pull_request.title = body.title
        if body.body is not None:
            pull_request.body = body.body
        if body.state is not None:
            if body.state not in (IssueState.OPEN, IssueState.CLOSED, IssueState.MERGED):
                raise HTTPException(status_code=400, detail="State must be 'open', 'closed', or 'merged'")
            pull_request.state = body.state

        pull_request.updated_at = datetime.now(UTC)
        await self.pull_request_store.update(pull_request)

        if self.activity_service is not None and body.state is not None:
            kind = {
                IssueState.MERGED: ActivityKind.PULL_REQUEST_MERGE,
                IssueState.CLOSED: ActivityKind.PULL_REQUEST_CLOSE,
            }.get(body.state, ActivityKind.PULL_REQUEST_REOPEN)
            repository = await self.repository_store.get_by_path(repo_path)
            await self.activity_service.record(
                actor=None,
                repo=repository,
                kind=kind,
                title=pull_request.title,
                target_type=ActivityTargetType.PULL_REQUEST,
                target_number=pull_request.number,
            )

        return self._to_public(pull_request, repo_path)

    async def _find_pull_request(self, repo_path: str, number: int) -> PullRequest:
        """Find a pull request by repository path and number.

        Args:
            repo_path: Normalized repository path.
            number: Pull request number.

        Returns:
            The pull request entity.

        Raises:
            HTTPException: If the repository or pull request is not found.
        """
        repository = await self.repository_store.get_by_path(repo_path)
        if repository is None:
            raise HTTPException(status_code=404, detail="Pull request not found")

        pull_request = await self.pull_request_store.get_by_number(repository.id, number)
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
