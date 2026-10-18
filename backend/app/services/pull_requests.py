"""Service for repository pull requests."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from fastapi import HTTPException

from app.clients.git.types import MergeRequest
from app.entities.activity import ActivityKind, ActivityTargetType
from app.entities.issues import IssueState
from app.entities.pull_requests import PullRequest
from app.schemas.repositories import (
    CommitsPublic,
    CompareResult,
    MergeMethod,
    MergeSettings,
    PullRequestCreate,
    PullRequestMerge,
    PullRequestMergeability,
    PullRequestPublic,
    PullRequestsListPublic,
    PullRequestUpdate,
)
from app.services.repositories import ensure_repository
from app.utils.markdown import render_markdown

if TYPE_CHECKING:
    from app.clients.git.merges import GitMergeClient
    from app.clients.pull_requests import PullRequestStore
    from app.clients.repositories import RepositoryStore
    from app.entities.users import User
    from app.schemas.activity import ActivityPublic
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
        git_merges: GitMergeClient,
    ) -> None:
        """Initialize the pull request service.

        Args:
            pull_request_store: Pull request store.
            repository_store: Repository store.
            repository_service: Repository service used to diff refs.
            activity_service: Service used to record activity.
            git_merges: Durable Git merge storage adapter.
        """
        self.pull_request_store = pull_request_store
        self.repository_store = repository_store
        self.repository_service = repository_service
        self.activity_service = activity_service
        self.git_merges = git_merges

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

    async def get_pull_request_events(self, owner: str, name: str, number: int) -> list[ActivityPublic]:
        """Read state events after verifying the pull request exists."""
        pull = await self._find_pull_request(owner, name, number)
        return await self.activity_service.pull_request_events(pull.repo_id, number)

    async def get_pull_request_commits(
        self, owner: str, name: str, number: int, offset: int = 0, limit: int = 50
    ) -> CommitsPublic:
        """Return the head branch's commits that are not already in the base branch."""
        pull = await self._find_pull_request(owner, name, number)
        return await self.repository_service.compare_commits(
            owner, name, pull.merge_base or pull.base_branch, pull.merged_head_commit or pull.head_branch, offset, limit
        )

    async def get_pull_request_files(
        self, owner: str, name: str, number: int, *, include_diff: bool = True
    ) -> CompareResult:
        """List the files changed between a pull request's base and head branches.

        Args:
            owner: Owner name.
            name: Repository name.
            number: Pull request number.
            include_diff: Include highlighted hunks or only the compact file index.

        Returns:
            CompareResult with the changed files and the resolved head commit.

        Raises:
            HTTPException: If the pull request is not found.
        """
        pull_request = await self._find_pull_request(owner, name, number)
        return await self.repository_service.compare(
            owner,
            name,
            pull_request.merge_base or pull_request.base_branch,
            pull_request.merged_head_commit or pull_request.head_branch,
            include_diff=include_diff,
        )

    async def get_mergeability(
        self, owner: str, name: str, number: int, method: MergeMethod
    ) -> PullRequestMergeability:
        """Check current branch tips independently of the PR conversation and file diff."""
        pull = await self._find_pull_request(owner, name, number)
        if pull.state != IssueState.OPEN:
            return PullRequestMergeability(mergeable=False, reason="Only open pull requests can be merged")
        repository = await self.repository_store.get_by_owner_and_name(owner, name)
        enabled = {
            MergeMethod.MERGE: repository.allow_merge_commit,
            MergeMethod.SQUASH: repository.allow_squash_merge,
            MergeMethod.REBASE: repository.allow_rebase_merge,
        }[method]
        if not enabled:
            return PullRequestMergeability(
                mergeable=False, reason="This merge method is disabled in repository settings"
            )
        if pull.head_branch == pull.base_branch:
            return PullRequestMergeability(mergeable=False, reason="The PR must have different base and head branches")
        completed = await self.git_merges.completed(owner, name, pull.id)
        if completed:
            return PullRequestMergeability(mergeable=True, base_commit=completed.base, head_commit=completed.head)
        base, head = await self.repository_service.branch_heads(owner, name, pull.base_branch, pull.head_branch)
        if base is None or head is None:
            return PullRequestMergeability(mergeable=False, reason="The base or PR branch no longer exists")
        return await self.git_merges.check(owner, name, base, head, method)

    async def merge_pull_request(
        self, owner: str, name: str, number: int, body: PullRequestMerge, current_user: User
    ) -> PullRequestPublic:
        """Apply an enabled Git strategy, then record the immutable merge and timeline event."""
        repository = await self.repository_store.get_by_owner_and_name(owner, name)
        if current_user.id != repository.owner_id and not current_user.is_superuser:
            raise HTTPException(status_code=403, detail="Only the repository owner can merge pull requests")
        pull = await self.pull_request_store.get_for_merge(repository.id, number)
        if pull.state == IssueState.MERGED:
            return self._to_public(pull, owner, name)
        if pull.state != IssueState.OPEN:
            raise HTTPException(status_code=409, detail="Only open pull requests can be merged")
        policies = MergeSettings.model_validate(repository, from_attributes=True)
        enabled, template = {
            "merge": (policies.allow_merge_commit, policies.merge_commit_message),
            "squash": (policies.allow_squash_merge, policies.squash_commit_message),
            "rebase": (policies.allow_rebase_merge, policies.rebase_commit_message),
        }[body.method]
        if not enabled:
            raise HTTPException(status_code=409, detail="This merge method is disabled in repository settings")
        if pull.head_branch == pull.base_branch:
            raise HTTPException(status_code=409, detail="The PR must have different base and head branches")
        result = await self.git_merges.completed(owner, name, pull.id)
        if result is None:
            result = await self.git_merges.merge(
                MergeRequest(
                    owner=owner,
                    name=name,
                    number=number,
                    pull_id=pull.id,
                    base_branch=pull.base_branch,
                    head_branch=pull.head_branch,
                    method=body.method,
                    template=template,
                    title=pull.title,
                    body=pull.body,
                    identity=f"{current_user.name} <{current_user.email}>".encode(),
                    delete_branch=policies.delete_branch_on_merge and pull.head_branch != repository.default_branch,
                    expected_base=body.base_commit,
                    expected_head=body.head_commit,
                )
            )
        pull.state, pull.has_merged = IssueState.MERGED, True
        pull.merge_base, pull.merged_head_commit, pull.merged_commit_id = result.base, result.head, result.commit
        pull.updated_at = datetime.now(UTC)
        await self.pull_request_store.update(pull)
        await self.activity_service.record(
            actor=current_user,
            repo=repository,
            kind=ActivityKind.PULL_REQUEST_MERGE,
            title=pull.title,
            target_type=ActivityTargetType.PULL_REQUEST,
            target_number=number,
        )
        return self._to_public(pull, owner, name)

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
            HTTPException: If the pull request is not found, the state is invalid, or the user is not allowed to edit.
        """
        if body.state == IssueState.MERGED:
            return await self.merge_pull_request(owner, name, number, PullRequestMerge(), current_user)
        pull_request = await self._find_pull_request(owner, name, number)

        if pull_request.state == IssueState.MERGED and body.state is not None and body.state != IssueState.MERGED:
            raise HTTPException(status_code=409, detail="A merged pull request cannot be reopened or closed")

        if (
            (body.title is not None or body.body is not None)
            and pull_request.author_id != current_user.id
            and not current_user.is_superuser
        ):
            raise HTTPException(status_code=403, detail="You can only edit your own pull requests")

        state_changed = body.state is not None and body.state != pull_request.state
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

        if state_changed:
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
            body_html=render_markdown(pr.body or ""),
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
