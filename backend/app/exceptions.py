"""Domain exceptions raised by the client (store) layer."""

from __future__ import annotations


class NotFoundError(Exception):
    """Base class for a requested entity that could not be found."""

    default_detail = "Not found"

    def __init__(self, detail: str | None = None) -> None:
        """Initialize the exception.

        Args:
            detail: Optional message overriding the default.
        """
        self.detail = detail or self.default_detail
        super().__init__(self.detail)


class RepositoryNotFoundError(NotFoundError):
    """Raised when a repository cannot be found."""

    default_detail = "Repository not found"


class UserNotFoundError(NotFoundError):
    """Raised when a user cannot be found."""

    default_detail = "User not found"


class OrganizationNotFoundError(NotFoundError):
    """Raised when an organization cannot be found."""

    default_detail = "Organization not found"


class OwnerNotFoundError(NotFoundError):
    """Raised when a repository owner (user or organization) cannot be found."""

    default_detail = "Owner not found"


class IssueNotFoundError(NotFoundError):
    """Raised when an issue cannot be found."""

    default_detail = "Issue not found"


class PullRequestNotFoundError(NotFoundError):
    """Raised when a pull request cannot be found."""

    default_detail = "Pull request not found"


class ReleaseNotFoundError(NotFoundError):
    """Raised when a release cannot be found."""

    default_detail = "Release not found"
