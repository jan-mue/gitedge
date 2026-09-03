"""Repository Pydantic schemas."""

from pydantic import BaseModel


class Repository(BaseModel):
    """Repository schema."""

    name: str
    path: str


class RepositoriesPublic(BaseModel):
    """List of repositories."""

    data: list[Repository]
    count: int


class TreeEntry(BaseModel):
    """A single entry in a Git tree (file or directory)."""

    name: str
    path: str
    type: str  # "tree" or "blob"
    size: int | None = None


class TreeListing(BaseModel):
    """Directory listing for a repository path."""

    entries: list[TreeEntry]
    repo_path: str
    tree_path: str
    ref: str


class FileContent(BaseModel):
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


class CreateRepositoryRequest(BaseModel):
    """Request to create a new repository."""

    name: str
    owner: str
