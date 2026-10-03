"""Repository Pydantic schemas."""

import uuid
from datetime import datetime

from app.schemas.base import GitEdgeBaseModel


class Repository(GitEdgeBaseModel):
    """Repository schema."""

    name: str
    path: str


class RepositoriesPublic(GitEdgeBaseModel):
    """List of repositories."""

    data: list[Repository]
    count: int


class TreeEntry(GitEdgeBaseModel):
    """A single entry in a Git tree (file or directory)."""

    name: str
    path: str
    type: str  # "tree" or "blob"
    size: int | None = None


class TreeListing(GitEdgeBaseModel):
    """Directory listing for a repository path."""

    entries: list[TreeEntry]
    repo_path: str
    tree_path: str
    ref: str


class FileContent(GitEdgeBaseModel):
    """File content with syntax highlighting."""

    name: str
    path: str
    size: int
    content: str
    highlighted_html: str
    css: str
    css_dark: str
    language: str
    line_count: int


class CreateRepositoryRequest(GitEdgeBaseModel):
    """Request to create a new repository."""

    name: str
    owner: str


class CommitInfo(GitEdgeBaseModel):
    """Information about a commit."""

    sha: str
    message: str
    author: str
    timestamp: int


class RepositoryInfo(GitEdgeBaseModel):
    """Extended repository information with metadata."""

    name: str
    path: str
    default_branch: str
    branch_count: int
    tag_count: int
    last_commit: CommitInfo | None = None


class ReadmeContent(GitEdgeBaseModel):
    """README file content."""

    filename: str
    content: str
    html: str


class BranchInfo(GitEdgeBaseModel):
    """Information about a branch."""

    name: str
    is_default: bool


class IssueCreate(GitEdgeBaseModel):
    """Request to create a new issue."""

    title: str
    body: str | None = None


class IssueUpdate(GitEdgeBaseModel):
    """Request to update an issue."""

    title: str | None = None
    body: str | None = None
    state: str | None = None


class IssuePublic(GitEdgeBaseModel):
    """Public issue representation."""

    id: uuid.UUID
    repo_path: str
    number: int
    title: str
    body: str | None = None
    state: str
    author_email: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class IssuesListPublic(GitEdgeBaseModel):
    """List of issues."""

    data: list[IssuePublic]
    count: int
    open_count: int
    closed_count: int


class PullRequestCreate(GitEdgeBaseModel):
    """Request to create a new pull request."""

    title: str
    body: str | None = None
    head_branch: str
    base_branch: str = "main"


class PullRequestUpdate(GitEdgeBaseModel):
    """Request to update a pull request."""

    title: str | None = None
    body: str | None = None
    state: str | None = None


class PullRequestPublic(GitEdgeBaseModel):
    """Public pull request representation."""

    id: uuid.UUID
    repo_path: str
    number: int
    title: str
    body: str | None = None
    state: str
    head_branch: str
    base_branch: str
    author_email: str | None = None
    merge_base: str | None = None
    merged_commit_id: str | None = None
    has_merged: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PullRequestsListPublic(GitEdgeBaseModel):
    """List of pull requests."""

    data: list[PullRequestPublic]
    count: int
    open_count: int
    closed_count: int
