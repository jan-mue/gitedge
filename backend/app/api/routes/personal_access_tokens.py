"""Account settings endpoints for personal access token lifecycle."""

import uuid

from fastapi import APIRouter, Response

from app.api.dependencies import CurrentUser, PersonalAccessTokenServiceDep
from app.schemas.personal_access_tokens import (
    PersonalAccessTokenCreate,
    PersonalAccessTokenIssued,
    PersonalAccessTokenPublic,
    PersonalAccessTokenRevoke,
)

router = APIRouter(prefix="/users/me/personal-access-tokens", tags=["personal-access-tokens"])


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
    service: PersonalAccessTokenServiceDep,
    current_user: CurrentUser,
    response: Response,
) -> PersonalAccessTokenIssued:
    """Generate a token and show its full value once."""
    response.headers["Cache-Control"] = "private, no-store"
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
    service: PersonalAccessTokenServiceDep,
    current_user: CurrentUser,
    response: Response,
) -> PersonalAccessTokenIssued:
    """Atomically replace a token, showing the replacement once."""
    response.headers["Cache-Control"] = "private, no-store"
    return await service.rotate(token_id, body, current_user)
