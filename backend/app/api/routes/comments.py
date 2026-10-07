"""Issue and pull request comment routes."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.dependencies import CommentServiceDep, CurrentUser
from app.schemas.comments import CommentCreate, CommentPublic, CommentsPublic

router = APIRouter(prefix="/repositories", tags=["comments"])


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
