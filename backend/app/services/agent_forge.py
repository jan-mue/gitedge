"""Authorized forge operations for agent capability tools."""

import uuid
from typing import TYPE_CHECKING

from app.exceptions import InvalidInputError, PermissionDeniedError
from app.schemas.repositories import (
    IssueCreate,
    IssuePublic,
    IssueUpdate,
    PullRequestCreate,
    PullRequestPublic,
    PullRequestUpdate,
)

if TYPE_CHECKING:
    from pydantic_ai.workspaces import Workspace

    from app.agents.dependencies import AgentForgeScope
    from app.clients.agent_repositories import AgentRepositoryClient
    from app.clients.repositories import RepositoryStore
    from app.clients.users import UserStore
    from app.entities.repositories import Repository
    from app.entities.users import User
    from app.services.authorization import AuthorizationService
    from app.services.issues import IssueService
    from app.services.pull_requests import PullRequestService


class AgentForgeService:
    """Keep identity checks and domain orchestration out of tool implementations."""

    def __init__(
        self,
        sources: AgentRepositoryClient,
        repositories: RepositoryStore,
        users: UserStore,
        authorization: AuthorizationService,
        pulls: PullRequestService,
        issues: IssueService,
    ) -> None:
        """Use the normal GitEdge stores, authorization and repository services."""
        self.sources = sources
        self.repositories = repositories
        self.users = users
        self.authorization = authorization
        self.pulls = pulls
        self.issues = issues

    async def authorize(self, scope: AgentForgeScope, repository: str, permission: str) -> tuple[Repository, User]:
        """Restrict every operation to the selected repositories and current account permissions."""
        owner, separator, name = repository.partition("/")
        if not separator or not owner or not name or "/" in name:
            raise InvalidInputError("Use a repository in owner/name format")
        repo = await self.repositories.get_by_owner_and_name(owner, name)
        if repo.id not in scope.repository_ids:
            raise PermissionDeniedError("Repository is not selected in this environment")
        user = await self.users.get(scope.user_id)
        await self.authorization.require(repo, user, permission)
        return repo, user

    async def create_pull_request(
        self,
        scope: AgentForgeScope,
        workspace: Workspace,
        repository: str,
        title: str,
        body: str,
        base: str | None,
        head: str,
    ) -> PullRequestPublic:
        """Publish the agent's existing Git commits and create or reuse its PR."""
        repo, user = await self.authorize(scope, repository, "pull_requests:write")
        await self.authorization.require(repo, user, "git:write")
        base_branch = base or repo.default_branch
        branch = await self.sources.publish_branch(workspace, repo.id, scope.session_id, base_branch, head)
        return await self.pulls.create_pull_request(
            repo.owner.name,
            repo.name,
            PullRequestCreate(title=title, body=body, head_branch=branch, base_branch=base_branch),
            user,
            pull_id=uuid.uuid5(scope.session_id, f"pull:{repo.id}:{branch}:{base_branch}"),
        )

    async def update_pull_request(
        self,
        scope: AgentForgeScope,
        workspace: Workspace,
        repository: str,
        number: int,
        body: PullRequestUpdate,
    ) -> PullRequestPublic:
        """Update a PR and publish already-committed changes from its conversation branch."""
        repo, user = await self.authorize(scope, repository, "pull_requests:write")
        pull = await self.pulls.get_pull_request(repo.owner.name, repo.name, number)
        publication_id = uuid.uuid5(scope.session_id, f"pull:{repo.id}:{pull.head_branch}:{pull.base_branch}")
        if pull.id == publication_id:
            await self.authorization.require(repo, user, "git:write")
            await self.sources.publish_branch(
                workspace,
                repo.id,
                scope.session_id,
                pull.base_branch,
                pull.head_branch,
            )
        return await self.pulls.update_pull_request(repo.owner.name, repo.name, number, body, user)

    async def create_issue(
        self, scope: AgentForgeScope, repository: str, body: IssueCreate, call_id: str
    ) -> IssuePublic:
        """Create an issue with a stable identity for retries of the same tool call."""
        repo, user = await self.authorize(scope, repository, "issues:write")
        return await self.issues.create_issue(
            repo.owner.name, repo.name, body, user, issue_id=uuid.uuid5(scope.session_id, f"issue:{call_id}")
        )

    async def update_issue(
        self, scope: AgentForgeScope, repository: str, number: int, body: IssueUpdate
    ) -> IssuePublic:
        """Update an issue using the same author/moderation policy as the repository API."""
        repo, user = await self.authorize(scope, repository, "issues:write")
        return await self.issues.update_issue(repo.owner.name, repo.name, number, body, user)
