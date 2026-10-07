"""Repository management routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.dependencies import (
    CurrentUser,
    IssueServiceDep,
    PullRequestServiceDep,
    RepositoryServiceDep,
)
from app.schemas.repositories import (
    BranchInfo,
    CommitDetail,
    CommitsPublic,
    CompareResult,
    CreateRepositoryRequest,
    FileContent,
    IssueCreate,
    IssuePublic,
    IssuesListPublic,
    IssueUpdate,
    PullRequestCreate,
    PullRequestPublic,
    PullRequestsListPublic,
    PullRequestUpdate,
    ReadmeContent,
    RepositoriesPublic,
    Repository,
    RepositoryInfo,
    TreeListing,
)

router = APIRouter(prefix="/repositories", tags=["repositories"])


@router.get("/")
async def list_repositories(repository_service: RepositoryServiceDep) -> RepositoriesPublic:
    """List all repositories."""
    return await repository_service.list_repositories()


@router.post("/", status_code=201)
async def create_repository(body: CreateRepositoryRequest, repository_service: RepositoryServiceDep) -> Repository:
    """Create a new empty Git repository."""
    return await repository_service.create_repository(body.owner, body.name)


@router.get("/{owner}/{repo}/tree")
async def get_tree(
    owner: str, repo: str, repository_service: RepositoryServiceDep, ref: str = "main", tree_path: str = ""
) -> TreeListing:
    """Get directory listing for a repository path."""
    return await repository_service.get_tree(owner, repo, ref, tree_path)


@router.get("/{owner}/{repo}/blob")
async def get_blob(
    owner: str, repo: str, repository_service: RepositoryServiceDep, ref: str = "main", file_path: str = ""
) -> FileContent:
    """Get file content with syntax highlighting."""
    return await repository_service.get_blob(owner, repo, ref, file_path)


@router.get("/{owner}/{repo}/info")
async def get_repository_info(
    owner: str, repo: str, repository_service: RepositoryServiceDep, ref: str = "main"
) -> RepositoryInfo:
    """Get extended repository information."""
    return await repository_service.get_info(owner, repo, ref)


@router.get("/{owner}/{repo}/readme")
async def get_readme(
    owner: str, repo: str, repository_service: RepositoryServiceDep, ref: str = "main", tree_path: str = ""
) -> ReadmeContent:
    """Get README content from a repository directory."""
    return await repository_service.get_readme(owner, repo, ref, tree_path)


@router.get("/{owner}/{repo}/branches")
async def list_branches(owner: str, repo: str, repository_service: RepositoryServiceDep) -> list[BranchInfo]:
    """List all branches in a repository."""
    return await repository_service.list_branches(owner, repo)


@router.get("/{owner}/{repo}/commits")
async def list_commits(
    owner: str, repo: str, repository_service: RepositoryServiceDep, ref: str = "main", offset: int = 0, limit: int = 50
) -> CommitsPublic:
    """List commit history for a repository ref."""
    return await repository_service.list_commits(owner, repo, ref, offset, limit)


@router.get("/{owner}/{repo}/commits/{sha}")
async def get_commit(owner: str, repo: str, sha: str, repository_service: RepositoryServiceDep) -> CommitDetail:
    """Get a single commit with its diff."""
    return await repository_service.get_commit(owner, repo, sha)


@router.get("/{owner}/{repo}/issues")
async def list_issues(
    owner: str,
    repo: str,
    issue_service: IssueServiceDep,
    state: Annotated[str, Query(description="Filter by state: open, closed, or all")] = "all",
) -> IssuesListPublic:
    """List issues for a repository."""
    return await issue_service.list_issues(owner, repo, state)


@router.post("/{owner}/{repo}/issues", status_code=201)
async def create_issue(
    owner: str, repo: str, body: IssueCreate, issue_service: IssueServiceDep, current_user: CurrentUser
) -> IssuePublic:
    """Create a new issue."""
    return await issue_service.create_issue(owner, repo, body, current_user)


@router.get("/{owner}/{repo}/issues/{number}")
async def get_issue(owner: str, repo: str, number: int, issue_service: IssueServiceDep) -> IssuePublic:
    """Get a single issue by number."""
    return await issue_service.get_issue(owner, repo, number)


@router.patch("/{owner}/{repo}/issues/{number}")
async def update_issue(
    owner: str, repo: str, number: int, body: IssueUpdate, issue_service: IssueServiceDep, current_user: CurrentUser
) -> IssuePublic:
    """Update an issue."""
    return await issue_service.update_issue(owner, repo, number, body, current_user)


@router.get("/{owner}/{repo}/pulls")
async def list_pull_requests(
    owner: str,
    repo: str,
    pull_request_service: PullRequestServiceDep,
    state: Annotated[str, Query(description="Filter by state: open, closed, merged, or all")] = "all",
) -> PullRequestsListPublic:
    """List pull requests for a repository."""
    return await pull_request_service.list_pull_requests(owner, repo, state)


@router.post("/{owner}/{repo}/pulls", status_code=201)
async def create_pull_request(
    owner: str,
    repo: str,
    body: PullRequestCreate,
    pull_request_service: PullRequestServiceDep,
    current_user: CurrentUser,
) -> PullRequestPublic:
    """Create a new pull request."""
    return await pull_request_service.create_pull_request(owner, repo, body, current_user)


@router.get("/{owner}/{repo}/pulls/{number}")
async def get_pull_request(
    owner: str, repo: str, number: int, pull_request_service: PullRequestServiceDep
) -> PullRequestPublic:
    """Get a single pull request by number."""
    return await pull_request_service.get_pull_request(owner, repo, number)


@router.get("/{owner}/{repo}/pulls/{number}/files")
async def get_pull_request_files(
    owner: str, repo: str, number: int, pull_request_service: PullRequestServiceDep
) -> CompareResult:
    """List the files changed by a pull request, diffed against its base branch."""
    return await pull_request_service.get_pull_request_files(owner, repo, number)


@router.patch("/{owner}/{repo}/pulls/{number}")
async def update_pull_request(
    owner: str,
    repo: str,
    number: int,
    body: PullRequestUpdate,
    pull_request_service: PullRequestServiceDep,
    current_user: CurrentUser,
) -> PullRequestPublic:
    """Update a pull request."""
    return await pull_request_service.update_pull_request(owner, repo, number, body, current_user)


@router.get("/{owner}/{repo}")
async def get_repository(owner: str, repo: str, repository_service: RepositoryServiceDep) -> Repository:
    """Get a specific repository."""
    return await repository_service.get_repository(owner, repo)
