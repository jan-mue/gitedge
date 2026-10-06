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
async def create_repository(
    body: CreateRepositoryRequest,
    repository_service: RepositoryServiceDep,
) -> Repository:
    """Create a new empty Git repository."""
    return await repository_service.create_repository(body.owner, body.name)


@router.get("/{path:path}/tree")
async def get_tree(
    path: str,
    repository_service: RepositoryServiceDep,
    ref: str = "main",
    tree_path: str = "",
) -> TreeListing:
    """Get directory listing for a repository path."""
    return await repository_service.get_tree(path, ref, tree_path)


@router.get("/{path:path}/blob")
async def get_blob(
    path: str,
    repository_service: RepositoryServiceDep,
    ref: str = "main",
    file_path: str = "",
) -> FileContent:
    """Get file content with syntax highlighting."""
    return await repository_service.get_blob(path, ref, file_path)


@router.get("/{path:path}/info")
async def get_repository_info(
    path: str,
    repository_service: RepositoryServiceDep,
    ref: str = "main",
) -> RepositoryInfo:
    """Get extended repository information."""
    return await repository_service.get_info(path, ref)


@router.get("/{path:path}/readme")
async def get_readme(
    path: str,
    repository_service: RepositoryServiceDep,
    ref: str = "main",
    tree_path: str = "",
) -> ReadmeContent:
    """Get README content from a repository directory."""
    return await repository_service.get_readme(path, ref, tree_path)


@router.get("/{path:path}/branches")
async def list_branches(path: str, repository_service: RepositoryServiceDep) -> list[BranchInfo]:
    """List all branches in a repository."""
    return await repository_service.list_branches(path)


@router.get("/{path:path}/commits")
async def list_commits(
    path: str,
    repository_service: RepositoryServiceDep,
    ref: str = "main",
    offset: int = 0,
    limit: int = 50,
) -> CommitsPublic:
    """List commit history for a repository ref."""
    return await repository_service.list_commits(path, ref, offset, limit)


@router.get("/{path:path}/commits/{sha}")
async def get_commit(path: str, sha: str, repository_service: RepositoryServiceDep) -> CommitDetail:
    """Get a single commit with its diff."""
    return await repository_service.get_commit(path, sha)


@router.get("/{path:path}/issues")
async def list_issues(
    path: str,
    issue_service: IssueServiceDep,
    state: Annotated[str, Query(description="Filter by state: open, closed, or all")] = "all",
) -> IssuesListPublic:
    """List issues for a repository."""
    return await issue_service.list_issues(path, state)


@router.post("/{path:path}/issues", status_code=201)
async def create_issue(
    path: str,
    body: IssueCreate,
    issue_service: IssueServiceDep,
    current_user: CurrentUser,
) -> IssuePublic:
    """Create a new issue."""
    return await issue_service.create_issue(path, body, current_user)


@router.get("/{path:path}/issues/{number}")
async def get_issue(path: str, number: int, issue_service: IssueServiceDep) -> IssuePublic:
    """Get a single issue by number."""
    return await issue_service.get_issue(path, number)


@router.patch("/{path:path}/issues/{number}")
async def update_issue(
    path: str,
    number: int,
    body: IssueUpdate,
    issue_service: IssueServiceDep,
) -> IssuePublic:
    """Update an issue."""
    return await issue_service.update_issue(path, number, body)


@router.get("/{path:path}/pulls")
async def list_pull_requests(
    path: str,
    pull_request_service: PullRequestServiceDep,
    state: Annotated[str, Query(description="Filter by state: open, closed, merged, or all")] = "all",
) -> PullRequestsListPublic:
    """List pull requests for a repository."""
    return await pull_request_service.list_pull_requests(path, state)


@router.post("/{path:path}/pulls", status_code=201)
async def create_pull_request(
    path: str,
    body: PullRequestCreate,
    pull_request_service: PullRequestServiceDep,
    current_user: CurrentUser,
) -> PullRequestPublic:
    """Create a new pull request."""
    return await pull_request_service.create_pull_request(path, body, current_user)


@router.get("/{path:path}/pulls/{number}")
async def get_pull_request(
    path: str,
    number: int,
    pull_request_service: PullRequestServiceDep,
) -> PullRequestPublic:
    """Get a single pull request by number."""
    return await pull_request_service.get_pull_request(path, number)


@router.get("/{path:path}/pulls/{number}/files")
async def get_pull_request_files(
    path: str,
    number: int,
    pull_request_service: PullRequestServiceDep,
) -> CompareResult:
    """List the files changed by a pull request, diffed against its base branch."""
    return await pull_request_service.get_pull_request_files(path, number)


@router.patch("/{path:path}/pulls/{number}")
async def update_pull_request(
    path: str,
    number: int,
    body: PullRequestUpdate,
    pull_request_service: PullRequestServiceDep,
) -> PullRequestPublic:
    """Update a pull request."""
    return await pull_request_service.update_pull_request(path, number, body)


@router.get("/{path:path}")
async def get_repository(path: str, repository_service: RepositoryServiceDep) -> Repository:
    """Get a specific repository by path."""
    return await repository_service.get_repository(path)
