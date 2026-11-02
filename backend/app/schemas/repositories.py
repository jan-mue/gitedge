"""Repository Pydantic schemas."""

import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import Field

from app.entities.issues import IssueState
from app.entities.repositories import MergeMessage
from app.schemas.base import GitEdgeBaseModel


class TreeEntryType(StrEnum):
    """Type of a Git tree entry."""

    TREE = "tree"
    BLOB = "blob"


class CommitChangeType(StrEnum):
    """How a file changed within a commit."""

    ADD = "add"
    MODIFY = "modify"
    DELETE = "delete"
    RENAME = "rename"


class MergeMethod(StrEnum):
    """Supported Git history strategies."""

    MERGE = "merge"
    SQUASH = "squash"
    REBASE = "rebase"


class MergeSettings(GitEdgeBaseModel):
    """Repository merge policies."""

    allow_merge_commit: bool = True
    allow_squash_merge: bool = True
    allow_rebase_merge: bool = True
    merge_commit_message: MergeMessage = MergeMessage.DEFAULT
    squash_commit_message: MergeMessage = MergeMessage.TITLE_DESCRIPTION
    rebase_commit_message: MergeMessage = MergeMessage.DEFAULT
    delete_branch_on_merge: bool = True


class PullRequestMerge(GitEdgeBaseModel):
    """Merge the expected PR revision using an enabled strategy."""

    method: MergeMethod = MergeMethod.MERGE
    head_commit: str | None = Field(default=None, pattern=r"^[0-9a-f]{40}$")
    base_commit: str | None = Field(default=None, pattern=r"^[0-9a-f]{40}$")


class PullRequestMergeability(GitEdgeBaseModel):
    """Read-only merge check for an exact pair of branch tips."""

    mergeable: bool
    base_commit: str | None = None
    head_commit: str | None = None
    conflicting_files: list[str] = Field(default_factory=list)
    reason: str | None = None


class Repository(MergeSettings):
    """Repository schema."""

    name: str
    owner: str
    description: str | None = None
    default_branch: str = "main"
    is_private: bool = False
    stars_count: int = 0
    forks_count: int = 0
    watchers_count: int = 0
    fork_of: str | None = None
    created_at: datetime
    updated_at: datetime


class RepositoriesPublic(GitEdgeBaseModel):
    """List of repositories."""

    data: list[Repository]
    count: int


class CommitInfo(GitEdgeBaseModel):
    """Information about a commit."""

    sha: str
    message: str
    author: str
    timestamp: int


class TreeEntry(GitEdgeBaseModel):
    """A single entry in a Git tree (file or directory)."""

    name: str
    path: str
    type: TreeEntryType
    size: int | None = None
    last_commit: CommitInfo | None = None


class TreeListing(GitEdgeBaseModel):
    """Directory listing for a repository path."""

    entries: list[TreeEntry]
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
    last_commit: CommitInfo | None = None


class CreateRepositoryRequest(GitEdgeBaseModel):
    """Request to create a new repository."""

    name: str
    owner: str


class RepositoryUpdate(GitEdgeBaseModel):
    """Editable repository settings."""

    allow_merge_commit: bool | None = None
    allow_squash_merge: bool | None = None
    allow_rebase_merge: bool | None = None
    merge_commit_message: MergeMessage | None = None
    squash_commit_message: MergeMessage | None = None
    rebase_commit_message: MergeMessage | None = None
    delete_branch_on_merge: bool | None = None
    name: str | None = Field(default=None, min_length=1, max_length=255, pattern=r"^[A-Za-z0-9_.-]+$")
    description: str | None = Field(default=None, max_length=10000)
    default_branch: str | None = Field(default=None, min_length=1, max_length=255)


class LanguageStatistic(GitEdgeBaseModel):
    """A language's share of source bytes in the selected revision."""

    name: str
    size: int
    percentage: float


class RepositoryStatistics(GitEdgeBaseModel):
    """Revision size and commit count, with language shares for text files."""

    commit_count: int = 0
    size: int = 0
    languages: list[LanguageStatistic] = Field(default_factory=list)


class FileIndex(GitEdgeBaseModel):
    """Searchable file paths at a revision."""

    paths: list[str]


class BlameLine(GitEdgeBaseModel):
    """A line attributed to its original commit."""

    number: int
    content: str
    commit: "CommitInfo"


class BlameContent(GitEdgeBaseModel):
    """File attribution at an immutable revision."""

    path: str
    revision: str
    lines: list[BlameLine]


class RepositoryInfo(GitEdgeBaseModel):
    """Extended repository information with metadata."""

    name: str
    owner: str
    description: str | None = None
    is_private: bool = False
    default_branch: str
    branch_count: int
    tag_count: int
    stars_count: int = 0
    forks_count: int = 0
    watchers_count: int = 0
    fork_of: str | None = None
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


class CommitListItem(GitEdgeBaseModel):
    """A single commit in a repository's history."""

    sha: str
    message: str
    author: str
    author_email: str
    timestamp: int


class CommitsPublic(GitEdgeBaseModel):
    """A page of commit history."""

    data: list[CommitListItem]
    count: int
    ref: str


class DiffToken(GitEdgeBaseModel):
    """A syntax token, optionally emphasized as an inline change."""

    text: str
    syntax: str = "text"
    changed: bool = False


class DiffLine(GitEdgeBaseModel):
    """A numbered line with server-generated syntax and change tokens."""

    kind: str
    old_line: int | None = None
    new_line: int | None = None
    tokens: list[DiffToken]
    no_newline: bool = False


class DiffRow(GitEdgeBaseModel):
    """Server-aligned line indexes for the split layout."""

    old: int | None = None
    new: int | None = None


class DiffHunk(GitEdgeBaseModel):
    """A unified hunk and its split layout."""

    header: str
    lines: list[DiffLine]
    rows: list[DiffRow]


class CommitFileChange(GitEdgeBaseModel):
    """A file changed by a commit, with its unified diff."""

    path: str
    old_path: str | None = None
    change_type: CommitChangeType
    additions: int
    deletions: int
    patch: str
    hunks: list[DiffHunk] = Field(default_factory=list)
    language: str = "Text"
    is_binary: bool = False
    diff_loaded: bool = True
    diff_line_count: int = 0


class CommitDetail(GitEdgeBaseModel):
    """Detailed information about a single commit."""

    sha: str
    message: str
    author: str
    author_email: str
    timestamp: int
    parents: list[str]
    files: list[CommitFileChange]
    additions: int
    deletions: int


class CompareResult(GitEdgeBaseModel):
    """The files changed between two refs, e.g. a pull request's base and head."""

    base_commit: str | None = None
    head_commit: str | None = None
    files: list[CommitFileChange]
    additions: int
    deletions: int


class IssueCreate(GitEdgeBaseModel):
    """Request to create a new issue."""

    title: str
    body: str | None = None


class IssueUpdate(GitEdgeBaseModel):
    """Request to update an issue."""

    title: str | None = None
    body: str | None = None
    state: IssueState | None = None


class IssuePublic(GitEdgeBaseModel):
    """Public issue representation."""

    id: uuid.UUID
    repo_owner: str
    repo_name: str
    number: int
    title: str
    body: str | None = None
    body_html: str
    state: IssueState
    author_username: str
    created_at: datetime
    updated_at: datetime


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
    state: IssueState | None = None


class PullRequestPublic(GitEdgeBaseModel):
    """Public pull request representation."""

    id: uuid.UUID
    repo_owner: str
    repo_name: str
    number: int
    title: str
    body: str | None = None
    body_html: str
    state: IssueState
    head_branch: str
    base_branch: str
    author_username: str
    merge_base: str | None = None
    merged_commit_id: str | None = None
    has_merged: bool = False
    created_at: datetime
    updated_at: datetime


class PullRequestsListPublic(GitEdgeBaseModel):
    """List of pull requests."""

    data: list[PullRequestPublic]
    count: int
    open_count: int
    closed_count: int
