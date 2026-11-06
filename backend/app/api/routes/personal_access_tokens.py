"""Account settings endpoints for personal access token lifecycle."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from fastapi import APIRouter, Response

from app.api.dependencies import AuthorizationServiceDep, CurrentUser, PersonalAccessTokenServiceDep
from app.exceptions import InvalidInputError
from app.schemas.personal_access_tokens import (
    PersonalAccessTokenCreate,
    PersonalAccessTokenIssued,
    PersonalAccessTokenPublic,
    PersonalAccessTokenRevoke,
    TokenRepositoryOption,
)

if TYPE_CHECKING:
    from app.entities.users import User

router = APIRouter(prefix="/users/me/personal-access-tokens", tags=["personal-access-tokens"])


async def validate_repositories(
    body: PersonalAccessTokenCreate, authorization: AuthorizationServiceDep, user: User
) -> None:
    """Require readable repositories before issuing or rotating an account token."""
    repositories = await authorization.repositories.get_by_ids(body.repository_ids)
    visible = await authorization.visible_repositories(repositories, user)
    if len(visible) != len(body.repository_ids):
        raise InvalidInputError("Select repositories you can access")


@router.get("/repositories")
async def repository_options(
    authorization: AuthorizationServiceDep, current_user: CurrentUser, response: Response
) -> list[TokenRepositoryOption]:
    """List repositories that this account can select for a token."""
    response.headers["Cache-Control"] = "private, no-store"
    repositories = await authorization.repositories.get_all(offset=0, limit=10000)
    return [
        TokenRepositoryOption(id=repository.id, name=repository.name, owner=repository.owner.name)
        for repository in await authorization.visible_repositories(repositories, current_user)
    ]


@router.get("/")
async def list_tokens(
    service: PersonalAccessTokenServiceDep, current_user: CurrentUser, response: Response
) -> list[PersonalAccessTokenPublic]:
    """List safe token metadata for the signed-in account."""
    response.headers["Cache-Control"] = "private, no-store"
    return await service.list_tokens(current_user)


@router.post("/", status_code=201)
async def create_token(
    body: PersonalAccessTokenCreate,
    authorization: AuthorizationServiceDep,
    service: PersonalAccessTokenServiceDep,
    current_user: CurrentUser,
    response: Response,
) -> PersonalAccessTokenIssued:
    """Generate a token and show its full value once."""
    response.headers["Cache-Control"] = "private, no-store"
    await validate_repositories(body, authorization, current_user)
    return await service.issue(body, current_user)


@router.post("/{token_id}/revoke", status_code=204)
async def revoke_token(
    token_id: uuid.UUID,
    body: PersonalAccessTokenRevoke,
    service: PersonalAccessTokenServiceDep,
    current_user: CurrentUser,
) -> None:
    """Revoke an account token without deleting its audit metadata."""
    await service.revoke(token_id, current_user, body.reason)


@router.post("/{token_id}/rotate", status_code=201)
async def rotate_token(
    token_id: uuid.UUID,
    body: PersonalAccessTokenCreate,
    authorization: AuthorizationServiceDep,
    service: PersonalAccessTokenServiceDep,
    current_user: CurrentUser,
    response: Response,
) -> PersonalAccessTokenIssued:
    """Atomically replace a token, showing the replacement once."""
    response.headers["Cache-Control"] = "private, no-store"
    await service.owned_token(token_id, current_user)
    await validate_repositories(body, authorization, current_user)
    return await service.rotate(token_id, body, current_user)
