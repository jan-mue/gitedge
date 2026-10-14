"""Permission dependencies composed with explicit authentication dependencies."""

from typing import TYPE_CHECKING, Annotated, get_args

from fastapi import Depends, HTTPException, Path, Request, Response, status
from fastapi.params import Depends as Dependency

from app.api.dependencies import AuthorizationServiceDep, OptionalUser
from app.entities.users import User

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

PermissionUser = User | None


def require_permission(
    permission: str | Callable[[Request], str],
    *,
    user_dep: object = OptionalUser,
    challenge: str = "Bearer",
) -> Callable[..., Awaitable[PermissionUser]]:
    """Authenticate and authorize a user for the named repository path."""
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
        action = permission if isinstance(permission, str) else permission(request)
        try:
            await authorization.require(repository, current_user, action)
        except HTTPException as error:
            if error.status_code == status.HTTP_401_UNAUTHORIZED:
                error.headers = {"WWW-Authenticate": challenge}
            raise
        if repository.is_private or current_user is not None:
            response.headers["Cache-Control"] = "private, no-store"
        return current_user

    return authorize
