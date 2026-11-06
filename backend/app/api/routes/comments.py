"""Issue and pull request comment routes."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.dependencies import CommentServiceDep, OptionalRepositoryUser, RepositoryUser
from app.api.permissions import require_comment_permission, require_permission
from app.entities.users import User
from app.schemas.comments import (
    CommentCreate,
    CommentPublic,
    CommentsPublic,
    CommentUpdate,
    ReactionCreate,
    ReactionsPublic,
)

router = APIRouter(prefix="/repositories", tags=["comments"])
comment_router = APIRouter(prefix="/comments", tags=["comments"])


@router.get(
    "/{owner}/{repo}/issues/{number}/comments",
    dependencies=[Depends(require_permission("repository:read", user_dep=OptionalRepositoryUser))],
)
async def list_comments(
    owner: str,
    repo: str,
    number: int,
    comment_service: CommentServiceDep,
) -> CommentsPublic:
    """List comments for an issue or pull request."""
    return await comment_service.list_comments(owner, repo, number)


@router.post("/{owner}/{repo}/issues/{number}/comments", status_code=201)
async def create_comment(
    owner: str,
    repo: str,
    number: int,
    body: CommentCreate,
    comment_service: CommentServiceDep,
    current_user: Annotated[
        User,
        Depends(require_permission("comments:write", user_dep=RepositoryUser)),
    ],
) -> CommentPublic:
    """Create a comment on an issue or pull request."""
    return await comment_service.create_comment(owner, repo, number, body, current_user)


@comment_router.patch("/{comment_id}")
async def update_comment(
    comment_id: uuid.UUID,
    body: CommentUpdate,
    comment_service: CommentServiceDep,
    current_user: Annotated[User, Depends(require_comment_permission("comments:write"))],
) -> CommentPublic:
    """Update a comment."""
    return await comment_service.update_comment(comment_id, body, current_user)


@comment_router.delete("/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(
    comment_id: uuid.UUID,
    comment_service: CommentServiceDep,
    current_user: Annotated[User, Depends(require_comment_permission("comments:write"))],
) -> None:
    """Delete a comment."""
    await comment_service.delete_comment(comment_id, current_user)


@comment_router.get("/{comment_id}/reactions")
async def list_reactions(
    comment_id: uuid.UUID,
    comment_service: CommentServiceDep,
    current_user: Annotated[
        User | None, Depends(require_comment_permission("repository:read", user_dep=OptionalRepositoryUser))
    ],
) -> ReactionsPublic:
    """List comment reactions."""
    return await comment_service.list_reactions(comment_id, current_user)


@comment_router.put("/{comment_id}/reactions")
async def add_reaction(
    comment_id: uuid.UUID,
    body: ReactionCreate,
    comment_service: CommentServiceDep,
    current_user: Annotated[User, Depends(require_comment_permission("comments:write"))],
) -> ReactionsPublic:
    """Add a reaction once per user and emoji."""
    return await comment_service.react(comment_id, body.emoji, current_user, enabled=True)


@comment_router.delete("/{comment_id}/reactions")
async def remove_reaction(
    comment_id: uuid.UUID,
    body: ReactionCreate,
    comment_service: CommentServiceDep,
    current_user: Annotated[User, Depends(require_comment_permission("comments:write"))],
) -> ReactionsPublic:
    """Remove the current user's reaction."""
    return await comment_service.react(comment_id, body.emoji, current_user, enabled=False)
