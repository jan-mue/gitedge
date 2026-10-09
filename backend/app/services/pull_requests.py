"""Service for repository pull requests."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from fastapi import HTTPException

from app.entities.activity import ActivityKind, ActivityTargetType
from app.entities.issues import IssueState
from app.entities.pull_requests import PullRequest
from app.schemas.repositories import (
    CompareResult,
    PullRequestCreate,
    PullRequestPublic,
    PullRequestsListPublic,
    PullRequestUpdate,
)
from app.services.repositories import ensure_repository

if TYPE_CHECKING:
    from app.clients.pull_requests import PullRequestStore
    from app.clients.repositories import RepositoryStore
    from app.entities.users import User
    from app.services.activity import ActivityService
    from app.services.repositories import RepositoryService


class PullRequestService:
    """Service for managing repository pull requests."""

    def __init__(
        self,
        pull_request_store: PullRequestStore,
        repository_store: RepositoryStore,
        repository_service: RepositoryService,
        activity_service: ActivityService,
    ) -> None:
        """Initialize the pull request service.

        Args:
            pull_request_store: Pull request store.
            repository_store: Repository store.
            repository_service: Repository service used to diff refs.
            activity_service: Service used to record activity.
        """
        self.pull_request_store = pull_request_store
        self.repository_store = repository_store
        self.repository_service = repository_service
        self.activity_service = activity_service

    async def list_pull_requests(self, owner: str, name: str, state: str) -> PullRequestsListPublic:
        """List pull requests for a repository.

        Args:
            owner: Owner name.
            name: Repository name.
            state: Filter by state (open, closed, merged, all).

        Returns:
            PullRequestsListPublic with the pull requests and counts.
        """
        repository = await self.repository_store.find_by_owner_and_name(owner, name)
        if repository is None:
            return PullRequestsListPublic(data=[], count=0, open_count=0, closed_count=0)

        filter_state = IssueState(state) if state in (IssueState.OPEN, IssueState.CLOSED, IssueState.MERGED) else None
        pull_requests = await self.pull_request_store.list_by_repo(repository.id, filter_state)

        return PullRequestsListPublic(
            data=[self._to_public(pr, owner, name) for pr in pull_requests],
            count=len(pull_requests),
            open_count=await self.pull_request_store.count_by_state(repository.id, IssueState.OPEN),
            closed_count=await self.pull_request_store.count_by_states(
                repository.id, [IssueState.CLOSED, IssueState.MERGED]
            ),
        )

    async def create_pull_request(
        self, owner: str, name: str, body: PullRequestCreate, current_user: User
    ) -> PullRequestPublic:
        """Create a new pull request.

        Args:
            owner: Owner name.
            name: Repository name.
            body: Pull request creation data.
            current_user: The authenticated user.

        Returns:
            The created pull request.
        """
        repository = await ensure_repository(self.repository_store, owner, name)

        pull_request = PullRequest(
            repo_id=repository.id,
            number=await self.pull_request_store.next_number(repository.id),
            title=body.title,
            body=body.body,
            state=IssueState.OPEN,
            author_id=current_user.id,
            head_repo_id=repository.id,
            base_repo_id=repository.id,
            head_branch=body.head_branch,
            base_branch=body.base_branch,
        )
        await self.pull_request_store.add(pull_request)
        pull_request.author = current_user

        await self.activity_service.record(
            actor=current_user,
            repo=repository,
            kind=ActivityKind.PULL_REQUEST_OPEN,
            title=pull_request.title,
            target_type=ActivityTargetType.PULL_REQUEST,
            target_number=pull_request.number,
        )

        return self._to_public(pull_request, owner, name)

    async def get_pull_request(self, owner: str, name: str, number: int) -> PullRequestPublic:
        """Get a single pull request by number.

        Args:
            owner: Owner name.
            name: Repository name.
            number: Pull request number.

        Returns:
            The pull request.

        Raises:
            HTTPException: If the pull request is not found.
        """
        pull_request = await self._find_pull_request(owner, name, number)
        return self._to_public(pull_request, owner, name)

    async def get_pull_request_files(self, owner: str, name: str, number: int) -> CompareResult:
        """List the files changed between a pull request's base and head branches.

        Args:
            owner: Owner name.
            name: Repository name.
            number: Pull request number.

        Returns:
            CompareResult with the changed files and the resolved head commit.

        Raises:
            HTTPException: If the pull request is not found.
        """
        pull_request = await self._find_pull_request(owner, name, number)
        return await self.repository_service.compare(owner, name, pull_request.base_branch, pull_request.head_branch)

    async def update_pull_request(
        self, owner: str, name: str, number: int, body: PullRequestUpdate, current_user: User
    ) -> PullRequestPublic:
        """Update a pull request.

        Args:
            owner: Owner name.
            name: Repository name.
            number: Pull request number.
            body: Fields to update.
            current_user: The authenticated user.

        Returns:
            The updated pull request.

        Raises:
            HTTPException: If the pull request is not found or the state is invalid.
        """
        pull_request = await self._find_pull_request(owner, name, number)

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

        if body.state is not None:
            kind = {
                IssueState.MERGED: ActivityKind.PULL_REQUEST_MERGE,
                IssueState.CLOSED: ActivityKind.PULL_REQUEST_CLOSE,
            }.get(body.state, ActivityKind.PULL_REQUEST_REOPEN)
            repository = await self.repository_store.get_by_owner_and_name(owner, name)
            await self.activity_service.record(
                actor=current_user,
                repo=repository,
                kind=kind,
                title=pull_request.title,
                target_type=ActivityTargetType.PULL_REQUEST,
                target_number=pull_request.number,
            )

        return self._to_public(pull_request, owner, name)

    async def _find_pull_request(self, owner: str, name: str, number: int) -> PullRequest:
        """Find a pull request by repository and number.

        Args:
            owner: Owner name.
            name: Repository name.
            number: Pull request number.

        Returns:
            The pull request entity.

        Raises:
            PullRequestNotFoundError: If the repository or pull request is not found.
        """
        repository = await self.repository_store.get_by_owner_and_name(owner, name)
        return await self.pull_request_store.get_by_number(repository.id, number)

    @staticmethod
    def _to_public(pr: PullRequest, owner: str, name: str) -> PullRequestPublic:
        """Convert a pull request entity to its public representation.

        Args:
            pr: The pull request entity (with its author loaded).
            owner: Owner name.
            name: Repository name.

        Returns:
            The public pull request representation.
        """
        return PullRequestPublic(
            id=pr.id,
            repo_owner=owner,
            repo_name=name,
            number=pr.number,
            title=pr.title,
            body=pr.body,
            state=pr.state,
            head_branch=pr.head_branch,
            base_branch=pr.base_branch,
            author_username=pr.author.name,
            merge_base=pr.merge_base,
            merged_commit_id=pr.merged_commit_id,
            has_merged=pr.has_merged,
            created_at=pr.created_at,
            updated_at=pr.updated_at,
        )
