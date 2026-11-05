"""Permission dependencies composed with explicit authentication dependencies."""

import uuid  # noqa: TC003 - FastAPI resolves the nested comment dependency at runtime.
from typing import TYPE_CHECKING, Annotated, get_args

from fastapi import Depends, Path, Request, Response
from fastapi.params import Depends as Dependency

from app.api.dependencies import AuthorizationServiceDep, CommentStoreDep, OptionalUser, RepositoryUser
from app.entities.users import User
from app.exceptions import AuthenticationError
from app.permissions import operation_policy
from app.services.personal_access_tokens import AuthenticatedToken

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable


PermissionUser = User | None


def require_permission(
    operation: str | Callable[[Request], str],
    *,
    user_dep: object = OptionalUser,
    challenge: str = "Bearer",
) -> Callable[..., Awaitable[PermissionUser]]:
    """Authenticate and enforce the central policy for one repository operation."""
    authentication = next((metadata for metadata in get_args(user_dep) if isinstance(metadata, Dependency)), None)
    if authentication is None:
        if not callable(user_dep):
            raise TypeError("user_dep must be an authentication callable or Annotated dependency alias")
        authentication = Depends(user_dep)

    async def authorize(
        owner: Annotated[str, Path()],
        repo: Annotated[str, Path()],
        request: Request,
        response: Response,
        authorization: AuthorizationServiceDep,
        current_user: Annotated[PermissionUser, authentication],
    ) -> PermissionUser:
        repository = await authorization.repositories.get_by_owner_and_name(owner, repo)
        action = operation if isinstance(operation, str) else operation(request)
        policy = operation_policy(action)
        require_token_access(request, repository.id, action)
        try:
            await authorization.require(repository, current_user, policy.permission)
        except AuthenticationError as error:
            error.challenge = challenge
            raise
        if repository.is_private or current_user is not None:
            response.headers["Cache-Control"] = "private, no-store"
        return current_user

    return authorize


def token_authentication(request: Request) -> AuthenticatedToken | None:
    """Read only verified, request-local token authentication state."""
    authenticated = getattr(request.state, "personal_access_token", None)
    return authenticated if isinstance(authenticated, AuthenticatedToken) else None


def require_token_access(request: Request, repository_id: uuid.UUID, operation: str) -> None:
    """Intersect a token's repository selection and operation permissions."""
    policy = operation_policy(operation)
    authenticated = token_authentication(request)
    if authenticated is not None:
        authenticated.require(repository_id, policy.token_scope)


def require_comment_permission(operation: str) -> Callable[..., Awaitable[User]]:
    """Resolve UUID-only comment routes before applying repository token restrictions."""
    operation_policy(operation)

    async def authorize(
        comment_id: uuid.UUID,
        request: Request,
        comments: CommentStoreDep,
        user: RepositoryUser,
    ) -> User:
        if token_authentication(request) is not None:
            comment = await comments.get(comment_id)
            _, repository = await comments.context(comment)
            require_token_access(request, repository.id, operation)
        return user

    return authorize
