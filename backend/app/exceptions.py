"""Application failures independent of the HTTP transport."""

from __future__ import annotations


class ApplicationError(Exception):
    """Base class for expected application failures."""

    default_detail = "Application error"

    def __init__(self, detail: str | None = None) -> None:
        """Initialize the exception.

        Args:
            detail: Optional message overriding the default.
        """
        self.detail = detail or self.default_detail
        super().__init__(self.detail)


class NotFoundError(ApplicationError):
    """A requested entity could not be found."""

    default_detail = "Not found"


class InvalidInputError(ApplicationError):
    """Input violates an application constraint."""

    default_detail = "Invalid input"


class UnprocessableInputError(ApplicationError):
    """A well-formed request contains invalid domain data."""


class PermissionDeniedError(ApplicationError):
    """The actor lacks permission for an operation."""

    default_detail = "Permission denied"


class AuthenticationError(ApplicationError):
    """Credentials are missing or cannot be authenticated."""

    default_detail = "Authentication required"
    default_challenge = "Bearer"

    def __init__(self, detail: str | None = None, *, challenge: str | None = None) -> None:
        """Keep the authentication scheme for the transport challenge."""
        super().__init__(detail)
        self.challenge = challenge or self.default_challenge


class ConflictError(ApplicationError):
    """An operation conflicts with current application state."""

    default_detail = "Conflict"


class PayloadTooLargeError(ApplicationError):
    """Input exceeds a supported processing limit."""

    default_detail = "Payload too large"


class RateLimitError(ApplicationError):
    """An operation exceeded its rate limit."""

    default_detail = "Rate limit exceeded"

    def __init__(self, detail: str | None = None, *, retry_after: int = 60) -> None:
        """Record the time in seconds until retrying is appropriate."""
        super().__init__(detail)
        self.retry_after = retry_after


class ServiceUnavailableError(ApplicationError):
    """An operation could not be completed temporarily."""

    default_detail = "Service unavailable"


class InvalidPersonalAccessTokenError(AuthenticationError):
    """A personal access token cannot authenticate its owner."""

    default_detail = "Invalid personal access token"
    default_challenge = 'Basic realm="GitEdge"'


class TokenNotFoundError(NotFoundError):
    """A token is absent or belongs to another account."""

    default_detail = "Token not found"


class TokenRevokedError(ConflictError):
    """A revoked token cannot be rotated."""

    default_detail = "Token is already revoked"


class TokenIssuanceError(ServiceUnavailableError):
    """Issuance exhausted its collision retries."""

    default_detail = "Could not issue a token; try again"


class TokenAuthenticationLimitError(RateLimitError):
    """A token exceeded its authentication attempt limit."""

    default_detail = "Token authentication limit reached"


class InsufficientTokenScopeError(PermissionDeniedError):
    """A token does not permit the requested Git operation."""

    default_detail = "Token lacks the required Git scope"


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


class CommentNotFoundError(NotFoundError):
    """Raised when a comment cannot be found or accessed."""

    default_detail = "Comment not found"


class PullRequestNotFoundError(NotFoundError):
    """Raised when a pull request cannot be found."""

    default_detail = "Pull request not found"


class ReleaseNotFoundError(NotFoundError):
    """Raised when a release cannot be found."""

    default_detail = "Release not found"


class EmailDeliveryError(Exception):
    """Raised when the email transport cannot deliver a message."""
