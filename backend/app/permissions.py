"""One repository operation determines both account and credential requirements."""

from dataclasses import dataclass

from app.exceptions import PermissionDeniedError
from app.schemas.personal_access_tokens import TokenScope


@dataclass(frozen=True)
class OperationPolicy:
    """The account permission and optional token scope required for an operation."""

    permission: str
    token_scope: TokenScope | None = None


REPOSITORY_OPERATIONS: dict[str, OperationPolicy] = {
    "repository:read": OperationPolicy("repository:read", TokenScope.REPOSITORY_READ),
    "repository:write": OperationPolicy("repository:admin", TokenScope.REPOSITORY_WRITE),
    "repository:delete": OperationPolicy("repository:owner", TokenScope.REPOSITORY_DELETE),
    "git:read": OperationPolicy("repository:read", TokenScope.READ),
    "git:write": OperationPolicy("repository:write", TokenScope.WRITE),
    "issues:write": OperationPolicy("repository:read", TokenScope.ISSUES_WRITE),
    "pull_requests:write": OperationPolicy("repository:read", TokenScope.PULL_REQUESTS_WRITE),
    "pull_requests:merge": OperationPolicy("repository:write", TokenScope.PULL_REQUESTS_MERGE),
    "comments:write": OperationPolicy("repository:read", TokenScope.COMMENTS_WRITE),
    "reviews:write": OperationPolicy("repository:read", TokenScope.REVIEWS_WRITE),
    "releases:write": OperationPolicy("repository:write", TokenScope.RELEASES_WRITE),
    "collaborators:read": OperationPolicy("repository:admin"),
    "collaborators:write": OperationPolicy("repository:admin"),
    "repository:fork": OperationPolicy("repository:read"),
    "stars:read": OperationPolicy("repository:read"),
    "stars:write": OperationPolicy("repository:read"),
    "watchers:read": OperationPolicy("repository:read"),
    "watchers:write": OperationPolicy("repository:read"),
}


def operation_policy(operation: str) -> OperationPolicy:
    """Reject unregistered operations rather than inferring permissive defaults."""
    policy = REPOSITORY_OPERATIONS.get(operation)
    if policy is None:
        raise PermissionDeniedError("Unsupported repository operation")
    return policy
