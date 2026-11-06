"""Permission dependencies composed with explicit authentication dependencies."""

import uuid  # noqa: TC003 - FastAPI resolves the nested comment dependency at runtime.
from typing import TYPE_CHECKING, Annotated, get_args

from fastapi import Depends, Path, Request, Response
from fastapi.params import Depends as Dependency

from app.api.dependencies import AuthorizationServiceDep, CommentStoreDep, OptionalUser, RepositoryUser
from app.entities.users import User
from app.exceptions import AuthenticationError
from app.services.personal_access_tokens import AuthenticatedToken

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable


PermissionUser = User | None


def _authentication(user_dep: object) -> Dependency:
    """Preserve explicit authentication metadata for repository and comment dependencies."""
    authentication = next((metadata for metadata in get_args(user_dep) if isinstance(metadata, Dependency)), None)
    if authentication is None:
        if not callable(user_dep):
            raise TypeError("user_dep must be an authentication callable or Annotated dependency alias")
        authentication = Depends(user_dep)
    return authentication


def require_permission(
    operation: str | Callable[[Request], str],
    *,
    user_dep: object = OptionalUser,
    challenge: str = "Bearer",
) -> Callable[..., Awaitable[PermissionUser]]:
    """Authenticate and enforce the central policy for one repository operation."""
    authentication = _authentication(user_dep)

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
        await require_token_access(request, repository.id, action)
        try:
            await authorization.require(repository, current_user, action)
        except AuthenticationError as error:
            error.challenge = challenge
            raise
        if repository.is_private or current_user is not None:
            response.headers["Cache-Control"] = "private, no-store"
        return current_user

    return authorize


def token_authentication(request: Request) -> AuthenticatedToken | None:
    """Read only verified, request-local token authentication state."""
    # TODO: Use a TypedDict for request state once https://github.com/fastapi/fastapi/pull/14863 is merged.
    authenticated = getattr(request.state, "personal_access_token", None)
    return authenticated if isinstance(authenticated, AuthenticatedToken) else None


async def require_token_access(request: Request, repository_id: uuid.UUID, operation: str) -> None:
    """Intersect a token's repository selection and operation permissions."""
    authenticated = token_authentication(request)
    if authenticated is not None:
        await authenticated.require(repository_id, operation)


def require_comment_permission(
    operation: str, *, user_dep: object = RepositoryUser
) -> Callable[..., Awaitable[PermissionUser]]:
    """Resolve UUID-only comment routes before applying repository token restrictions."""
    authentication = _authentication(user_dep)

    async def authorize(
        comment_id: uuid.UUID,
        request: Request,
        comments: CommentStoreDep,
        user: Annotated[PermissionUser, authentication],
    ) -> PermissionUser:
        if token_authentication(request) is not None:
            comment = await comments.get(comment_id)
            _, repository = await comments.context(comment)
            await require_token_access(request, repository.id, operation)
        return user

    return authorize
