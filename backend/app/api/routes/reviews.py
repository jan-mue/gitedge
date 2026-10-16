"""Pull request review and private workspace endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Path, Response

from app.api.dependencies import CurrentUser, ReviewServiceDep
from app.schemas.repositories import DiffHunk
from app.schemas.reviews import (
    ReviewDraft,
    ReviewedFileUpdate,
    ReviewPublic,
    ReviewReplyCreate,
    ReviewReplyPublic,
    ReviewSubmit,
    ReviewWorkspacePublic,
)

router = APIRouter(prefix="/repositories/{owner}/{repo}/pulls/{number}", tags=["reviews"])


@router.get("/reviews")
async def list_reviews(owner: str, repo: str, number: int, service: ReviewServiceDep) -> list[ReviewPublic]:
    """List submitted reviews and their published line comments."""
    return await service.list_reviews(owner, repo, number)


@router.get("/review-workspace")
async def get_workspace(
    owner: str, repo: str, number: int, response: Response, service: ReviewServiceDep, current_user: CurrentUser
) -> ReviewWorkspacePublic:
    """Read only the authenticated user's private draft and viewed status."""
    response.headers["Cache-Control"] = "private, no-store"
    return await service.get_workspace(owner, repo, number, current_user)


@router.get("/reviews/{review_id}/comments/{comment_index}/context")
async def get_comment_context(
    owner: str,
    repo: str,
    number: int,
    review_id: uuid.UUID,
    comment_index: Annotated[int, Path(ge=0)],
    service: ReviewServiceDep,
) -> DiffHunk:
    """Read a short highlighted snippet ending at the original comment anchor."""
    return await service.get_comment_context(owner, repo, number, review_id, comment_index)


@router.post("/reviews/{review_id}/replies", status_code=201)
async def reply_to_review(
    owner: str,
    repo: str,
    number: int,
    review_id: uuid.UUID,
    body: ReviewReplyCreate,
    service: ReviewServiceDep,
    current_user: CurrentUser,
) -> ReviewReplyPublic:
    """Reply to a published line comment or overall review comment."""
    return await service.reply(owner, repo, number, review_id, body, current_user)


@router.put("/review-draft")
async def save_draft(
    owner: str, repo: str, number: int, body: ReviewDraft, service: ReviewServiceDep, current_user: CurrentUser
) -> ReviewWorkspacePublic:
    """Save a private review draft, including line comments."""
    return await service.save_draft(owner, repo, number, body, current_user)


@router.put("/reviewed-files")
async def mark_reviewed(
    owner: str, repo: str, number: int, body: ReviewedFileUpdate, service: ReviewServiceDep, current_user: CurrentUser
) -> ReviewWorkspacePublic:
    """Update a file's reviewed state for the authenticated user."""
    return await service.mark_reviewed(owner, repo, number, body, current_user)


@router.post("/reviews", status_code=201)
async def submit_review(
    owner: str, repo: str, number: int, body: ReviewSubmit, service: ReviewServiceDep, current_user: CurrentUser
) -> ReviewPublic:
    """Publish a review with a comment, approval or request-changes outcome."""
    return await service.submit(owner, repo, number, body, current_user)
