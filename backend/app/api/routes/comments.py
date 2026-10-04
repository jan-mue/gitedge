"""Issue and pull request comment routes."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.dependencies import CommentServiceDep, CurrentUser
from app.schemas.comments import CommentCreate, CommentPublic, CommentsPublic

router = APIRouter(prefix="/repositories", tags=["comments"])


@router.get("/{path:path}/issues/{number}/comments")
async def list_comments(path: str, number: int, comment_service: CommentServiceDep) -> CommentsPublic:
    """List comments for an issue or pull request."""
    return await comment_service.list_comments(path, number)


@router.post("/{path:path}/issues/{number}/comments", status_code=201)
async def create_comment(
    path: str,
    number: int,
    body: CommentCreate,
    comment_service: CommentServiceDep,
    current_user: CurrentUser,
) -> CommentPublic:
    """Create a comment on an issue or pull request."""
    return await comment_service.create_comment(path, number, body, current_user)
