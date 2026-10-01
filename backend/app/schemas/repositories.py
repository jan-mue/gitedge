"""Repository Pydantic schemas."""

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
