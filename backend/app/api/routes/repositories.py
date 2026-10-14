"""Repository management routes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.api.dependencies import (
    AuthorizationServiceDep,
    CurrentUser,
    IssueServiceDep,
    OptionalUser,
    PullRequestServiceDep,
    RepositoryServiceDep,
)
from app.api.permissions import require_permission
from app.entities.users import User
from app.schemas.repositories import (
    BlameContent,
    BranchInfo,
    CommitDetail,
    CommitsPublic,
    CompareResult,
    CreateRepositoryRequest,
    FileContent,
    FileIndex,
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
    RepositoryStatistics,
    RepositoryUpdate,
    TreeListing,
)
from app.utils.cache_headers import is_commit_sha

router = APIRouter(prefix="/repositories", tags=["repositories"])

if TYPE_CHECKING:
    from app.services.repositories import RepositoryService


async def _apply_cache_headers(
    response: Response,
    service: RepositoryService,
    owner: str,
    repo: str,
    *,
    immutable: bool,
) -> None:
    """Apply CDN cache headers for repository content.

    Args:
        response: FastAPI response to annotate.
        service: Repository service that resolves repository privacy.
        owner: Repository owner.
        repo: Repository name.
        immutable: Whether the content is addressed by an immutable commit SHA.
    """
    headers = await service.cache_headers(owner, repo, immutable=immutable)
    for name, value in headers.items():
        response.headers[name] = value


@router.get("/")
async def list_repositories(repository_service: RepositoryServiceDep, user: OptionalUser) -> RepositoriesPublic:
    """List all repositories."""
    return await repository_service.list_repositories(user)


@router.post("/", status_code=201)
async def create_repository(
    body: CreateRepositoryRequest,
    repository_service: RepositoryServiceDep,
    user: CurrentUser,
    authorization: AuthorizationServiceDep,
) -> Repository:
    """Create a new empty Git repository."""
    await authorization.require_creation(body.owner, user)
    if body.name in (".", "..") or body.name.endswith(".git"):
        raise HTTPException(status_code=400, detail="Invalid repository name")
    if await authorization.repositories.find_by_owner_and_name(body.owner, body.name) is not None:
        raise HTTPException(status_code=409, detail="Repository already exists")
    return await repository_service.create_repository(body.owner, body.name, is_private=body.is_private)


@router.get(
    "/{owner}/{repo}/source", dependencies=[Depends(require_permission("repository:read", user_dep=OptionalUser))]
)
async def get_source(
    owner: str,
    repo: str,
    response: Response,
    repository_service: RepositoryServiceDep,
    ref: str = "HEAD",
    source_path: str = "",
) -> TreeListing | FileContent:
    """Resolve a directory or file in one source request."""
    result = await repository_service.get_source(owner, repo, ref, source_path)
    await _apply_cache_headers(response, repository_service, owner, repo, immutable=is_commit_sha(ref))
    return result


@router.get(
    "/{owner}/{repo}/tree", dependencies=[Depends(require_permission("repository:read", user_dep=OptionalUser))]
)
async def get_tree(
    owner: str,
    repo: str,
    response: Response,
    repository_service: RepositoryServiceDep,
    ref: str = "main",
    tree_path: str = "",
) -> TreeListing:
    """Get directory listing for a repository path."""
    result = await repository_service.get_tree(owner, repo, ref, tree_path)
    await _apply_cache_headers(response, repository_service, owner, repo, immutable=is_commit_sha(ref))
    return result


@router.get(
    "/{owner}/{repo}/blob", dependencies=[Depends(require_permission("repository:read", user_dep=OptionalUser))]
)
async def get_blob(
    owner: str,
    repo: str,
    response: Response,
    repository_service: RepositoryServiceDep,
    ref: str = "main",
    file_path: str = "",
) -> FileContent:
    """Get file content with syntax highlighting."""
    result = await repository_service.get_blob(owner, repo, ref, file_path)
    await _apply_cache_headers(response, repository_service, owner, repo, immutable=is_commit_sha(ref))
    return result


@router.get(
    "/{owner}/{repo}/blame", dependencies=[Depends(require_permission("repository:read", user_dep=OptionalUser))]
)
async def get_blame(
    owner: str,
    repo: str,
    response: Response,
    repository_service: RepositoryServiceDep,
    ref: str = "HEAD",
    file_path: str = "",
) -> BlameContent:
    """Get line attribution for a file at a revision."""
    result = await repository_service.get_blame(owner, repo, ref, file_path)
    await _apply_cache_headers(response, repository_service, owner, repo, immutable=is_commit_sha(ref))
    return result


@router.get(
    "/{owner}/{repo}/statistics", dependencies=[Depends(require_permission("repository:read", user_dep=OptionalUser))]
)
async def get_statistics(
    owner: str,
    repo: str,
    response: Response,
    repository_service: RepositoryServiceDep,
    ref: str = "HEAD",
) -> RepositoryStatistics:
    """Get byte-weighted language, size, and commit statistics."""
    result = await repository_service.get_statistics(owner, repo, ref)
    await _apply_cache_headers(response, repository_service, owner, repo, immutable=is_commit_sha(ref))
    return result


@router.get(
    "/{owner}/{repo}/files", dependencies=[Depends(require_permission("repository:read", user_dep=OptionalUser))]
)
async def get_file_index(
    owner: str,
    repo: str,
    response: Response,
    repository_service: RepositoryServiceDep,
    ref: str = "HEAD",
) -> FileIndex:
    """Get searchable file paths at a revision."""
    result = await repository_service.get_file_index(owner, repo, ref)
    await _apply_cache_headers(response, repository_service, owner, repo, immutable=is_commit_sha(ref))
    return result


@router.get("/{owner}/{repo}/raw", dependencies=[Depends(require_permission("repository:read", user_dep=OptionalUser))])
async def get_raw(
    owner: str,
    repo: str,
    repository_service: RepositoryServiceDep,
    ref: str = "HEAD",
    file_path: str = "",
) -> Response:
    """Serve original file bytes without interpreting repository content as HTML."""
    data = await repository_service.get_raw(owner, repo, ref, file_path)
    response = Response(data, media_type="text/plain", headers={"X-Content-Type-Options": "nosniff"})
    await _apply_cache_headers(response, repository_service, owner, repo, immutable=is_commit_sha(ref))
    return response


@router.get(
    "/{owner}/{repo}/info", dependencies=[Depends(require_permission("repository:read", user_dep=OptionalUser))]
)
async def get_repository_info(
    owner: str,
    repo: str,
    response: Response,
    repository_service: RepositoryServiceDep,
    ref: str = "main",
) -> RepositoryInfo:
    """Get extended repository information."""
    result = await repository_service.get_info(owner, repo, ref)
    await _apply_cache_headers(response, repository_service, owner, repo, immutable=False)
    return result


@router.get(
    "/{owner}/{repo}/readme", dependencies=[Depends(require_permission("repository:read", user_dep=OptionalUser))]
)
async def get_readme(
    owner: str,
    repo: str,
    response: Response,
    repository_service: RepositoryServiceDep,
    ref: str = "main",
    tree_path: str = "",
) -> ReadmeContent:
    """Get README content from a repository directory."""
    result = await repository_service.get_readme(owner, repo, ref, tree_path)
    await _apply_cache_headers(response, repository_service, owner, repo, immutable=is_commit_sha(ref))
    return result


@router.get(
    "/{owner}/{repo}/branches", dependencies=[Depends(require_permission("repository:read", user_dep=OptionalUser))]
)
async def list_branches(
    owner: str,
    repo: str,
    response: Response,
    repository_service: RepositoryServiceDep,
) -> list[BranchInfo]:
    """List all branches in a repository."""
    result = await repository_service.list_branches(owner, repo)
    await _apply_cache_headers(response, repository_service, owner, repo, immutable=False)
    return result


@router.get(
    "/{owner}/{repo}/commits", dependencies=[Depends(require_permission("repository:read", user_dep=OptionalUser))]
)
async def list_commits(
    owner: str,
    repo: str,
    response: Response,
    repository_service: RepositoryServiceDep,
    ref: str = "main",
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    file_path: str = "",
) -> CommitsPublic:
    """List commit history for a repository ref."""
    result = await repository_service.list_commits(owner, repo, ref, offset, limit, file_path)
    await _apply_cache_headers(response, repository_service, owner, repo, immutable=is_commit_sha(ref))
    return result


@router.get(
    "/{owner}/{repo}/commits/{sha}",
    dependencies=[Depends(require_permission("repository:read", user_dep=OptionalUser))],
)
async def get_commit(
    owner: str,
    repo: str,
    sha: str,
    response: Response,
    repository_service: RepositoryServiceDep,
) -> CommitDetail:
    """Get a single commit with its diff."""
    result = await repository_service.get_commit(owner, repo, sha)
    await _apply_cache_headers(response, repository_service, owner, repo, immutable=True)
    return result


@router.get(
    "/{owner}/{repo}/issues", dependencies=[Depends(require_permission("repository:read", user_dep=OptionalUser))]
)
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
    owner: str,
    repo: str,
    body: IssueCreate,
    issue_service: IssueServiceDep,
    current_user: Annotated[User, Depends(require_permission("repository:read", user_dep=CurrentUser))],
) -> IssuePublic:
    """Create a new issue."""
    return await issue_service.create_issue(owner, repo, body, current_user)


@router.get(
    "/{owner}/{repo}/issues/{number}",
    dependencies=[Depends(require_permission("repository:read", user_dep=OptionalUser))],
)
async def get_issue(
    owner: str,
    repo: str,
    number: int,
    issue_service: IssueServiceDep,
) -> IssuePublic:
    """Get a single issue by number."""
    return await issue_service.get_issue(owner, repo, number)


@router.patch("/{owner}/{repo}/issues/{number}")
async def update_issue(
    owner: str,
    repo: str,
    number: int,
    body: IssueUpdate,
    issue_service: IssueServiceDep,
    current_user: Annotated[User, Depends(require_permission("repository:read", user_dep=CurrentUser))],
) -> IssuePublic:
    """Update an issue."""
    return await issue_service.update_issue(owner, repo, number, body, current_user)


@router.get(
    "/{owner}/{repo}/pulls", dependencies=[Depends(require_permission("repository:read", user_dep=OptionalUser))]
)
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
    current_user: Annotated[User, Depends(require_permission("repository:read", user_dep=CurrentUser))],
) -> PullRequestPublic:
    """Create a new pull request."""
    return await pull_request_service.create_pull_request(owner, repo, body, current_user)


@router.get(
    "/{owner}/{repo}/pulls/{number}",
    dependencies=[Depends(require_permission("repository:read", user_dep=OptionalUser))],
)
async def get_pull_request(
    owner: str,
    repo: str,
    number: int,
    pull_request_service: PullRequestServiceDep,
) -> PullRequestPublic:
    """Get a single pull request by number."""
    return await pull_request_service.get_pull_request(owner, repo, number)


@router.get(
    "/{owner}/{repo}/pulls/{number}/files",
    dependencies=[Depends(require_permission("repository:read", user_dep=OptionalUser))],
)
async def get_pull_request_files(
    owner: str,
    repo: str,
    number: int,
    response: Response,
    pull_request_service: PullRequestServiceDep,
    repository_service: RepositoryServiceDep,
) -> CompareResult:
    """List the files changed by a pull request, diffed against its base branch."""
    result = await pull_request_service.get_pull_request_files(owner, repo, number)
    await _apply_cache_headers(response, repository_service, owner, repo, immutable=False)
    return result


@router.patch("/{owner}/{repo}/pulls/{number}")
async def update_pull_request(
    owner: str,
    repo: str,
    number: int,
    body: PullRequestUpdate,
    pull_request_service: PullRequestServiceDep,
    current_user: Annotated[User, Depends(require_permission("repository:read", user_dep=CurrentUser))],
) -> PullRequestPublic:
    """Update a pull request."""
    return await pull_request_service.update_pull_request(owner, repo, number, body, current_user)


@router.get("/{owner}/{repo}", dependencies=[Depends(require_permission("repository:read", user_dep=OptionalUser))])
async def get_repository(
    owner: str,
    repo: str,
    response: Response,
    repository_service: RepositoryServiceDep,
) -> Repository:
    """Get a specific repository."""
    result = await repository_service.get_repository(owner, repo)
    await _apply_cache_headers(response, repository_service, owner, repo, immutable=False)
    return result


@router.patch("/{owner}/{repo}")
async def update_repository(
    owner: str,
    repo: str,
    body: RepositoryUpdate,
    repository_service: RepositoryServiceDep,
    current_user: Annotated[User, Depends(require_permission("repository:admin", user_dep=CurrentUser))],
) -> Repository:
    """Update repository settings as the owner or administrator."""
    return await repository_service.update_repository(owner, repo, body, current_user)


@router.delete("/{owner}/{repo}", status_code=204)
async def delete_repository(
    owner: str,
    repo: str,
    repository_service: RepositoryServiceDep,
    current_user: Annotated[User, Depends(require_permission("repository:owner", user_dep=CurrentUser))],
) -> None:
    """Permanently delete a repository as the owner or administrator."""
    await repository_service.delete_repository(owner, repo, current_user)
