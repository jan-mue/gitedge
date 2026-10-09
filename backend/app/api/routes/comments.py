"""Issue and pull request comment routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from app.api.dependencies import CommentServiceDep, CurrentUser
from app.schemas.comments import CommentCreate, CommentPublic, CommentsPublic, CommentUpdate

router = APIRouter(prefix="/repositories", tags=["comments"])
comment_router = APIRouter(prefix="/comments", tags=["comments"])


@router.get("/{owner}/{repo}/issues/{number}/comments")
async def list_comments(owner: str, repo: str, number: int, comment_service: CommentServiceDep) -> CommentsPublic:
    """List comments for an issue or pull request."""
    return await comment_service.list_comments(owner, repo, number)


@router.post("/{owner}/{repo}/issues/{number}/comments", status_code=201)
async def create_comment(
    owner: str,
    repo: str,
    number: int,
    body: CommentCreate,
    comment_service: CommentServiceDep,
    current_user: CurrentUser,
) -> CommentPublic:
    """Create a comment on an issue or pull request."""
    return await comment_service.create_comment(owner, repo, number, body, current_user)


@comment_router.patch("/{comment_id}")
async def update_comment(
    comment_id: uuid.UUID, body: CommentUpdate, comment_service: CommentServiceDep, current_user: CurrentUser
) -> CommentPublic:
    """Update a comment."""
    return await comment_service.update_comment(comment_id, body, current_user)


@comment_router.delete("/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(comment_id: uuid.UUID, comment_service: CommentServiceDep, current_user: CurrentUser) -> None:
    """Delete a comment."""
    await comment_service.delete_comment(comment_id, current_user)
