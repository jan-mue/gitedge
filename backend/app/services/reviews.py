"""Pull request review validation and lifecycle."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException

from app.entities.issues import IssueState
from app.entities.reviews import PullRequestReview, PullRequestReviewReply
from app.schemas.reviews import (
    ReviewCommentPublic,
    ReviewDraft,
    ReviewedFileUpdate,
    ReviewLineComment,
    ReviewPublic,
    ReviewReplyCreate,
    ReviewReplyPublic,
    ReviewState,
    ReviewSubmit,
    ReviewWorkspacePublic,
)
from app.services.diffs import comment_context
from app.services.markdown import render_markdown

if TYPE_CHECKING:
    import uuid

    from app.clients.pull_requests import PullRequestStore
    from app.clients.repositories import RepositoryStore
    from app.clients.reviews import ReviewStore
    from app.entities.pull_requests import PullRequest
    from app.entities.reviews import PullRequestReviewWorkspace
    from app.entities.users import User
    from app.schemas.repositories import CommitFileChange, CompareResult, DiffHunk
    from app.services.repositories import RepositoryService


class ReviewService:
    """Manage private drafts, submitted reviews and viewed-file progress."""

    def __init__(
        self,
        store: ReviewStore,
        pull_requests: PullRequestStore,
        repositories: RepositoryStore,
        repository_service: RepositoryService,
    ) -> None:
        """Initialize persistence and Git comparison dependencies."""
        self.store = store
        self.pull_requests = pull_requests
        self.repositories = repositories
        self.repository_service = repository_service

    async def _pull(self, owner: str, repo: str, number: int) -> PullRequest:
        repository = await self.repositories.get_by_owner_and_name(owner, repo)
        return await self.pull_requests.get_by_number(repository.id, number)

    async def _comparison(self, owner: str, repo: str, pull: PullRequest) -> CompareResult:
        return await self.repository_service.compare(
            owner, repo, pull.base_branch, pull.head_branch, include_diff=False
        )

    @staticmethod
    def _validate_revision(body: ReviewDraft | ReviewedFileUpdate, comparison: CompareResult) -> None:
        if body.base_commit != comparison.base_commit or body.head_commit != comparison.head_commit:
            raise HTTPException(
                status_code=409, detail="The branches changed. Refresh the diff before continuing your review."
            )

    async def _validate_comments(
        self, owner: str, repo: str, comments: list[ReviewLineComment], comparison: CompareResult
    ) -> dict[str, CommitFileChange]:
        if not comments:
            return {}
        paths = {comment.path for comment in comments}
        files = {file.path: file for file in comparison.files if file.path in paths}
        if paths - files.keys():
            raise HTTPException(status_code=422, detail="File is not in this comparison")
        for path, file in files.items():
            if not file.diff_loaded:
                files[path] = await self.repository_service.get_diff_file(
                    owner, repo, comparison.head_commit or "", path, comparison.base_commit or ""
                )
        anchors = {
            (file.path, side, number)
            for file in files.values()
            for hunk in file.hunks
            for line in hunk.lines
            for side, number in (("old", line.old_line), ("new", line.new_line))
            if number is not None
        }
        for comment in comments:
            if not comment.body.strip() or (comment.path, comment.side, comment.line) not in anchors:
                raise HTTPException(
                    status_code=422, detail="Line comments must have text and refer to a visible diff line."
                )
        return files

    @staticmethod
    def _workspace_public(workspace: PullRequestReviewWorkspace, comparison: CompareResult) -> ReviewWorkspacePublic:
        current = workspace.base_commit == comparison.base_commit and workspace.head_commit == comparison.head_commit
        return ReviewWorkspacePublic(
            draft=ReviewDraft.model_validate(workspace.draft) if workspace.draft else None,
            reviewed_paths=workspace.reviewed_paths if current else [],
        )

    @staticmethod
    def _public(review: PullRequestReview) -> ReviewPublic:
        return ReviewPublic(
            id=review.id,
            author_username=review.author.name,
            created_at=review.created_at,
            state=ReviewState(review.state),
            body=review.body,
            base_commit=review.base_commit,
            head_commit=review.head_commit,
            comments=[ReviewCommentPublic.model_validate(comment) for comment in review.comments],
            replies=[ReviewService._reply_public(reply) for reply in review.replies],
        )

    @staticmethod
    def _reply_public(reply: PullRequestReviewReply) -> ReviewReplyPublic:
        return ReviewReplyPublic(
            id=reply.id,
            author_username=reply.author.name,
            created_at=reply.created_at,
            comment_index=reply.comment_index,
            body=reply.body,
            body_html=render_markdown(reply.body),
        )

    async def list_reviews(self, owner: str, repo: str, number: int) -> list[ReviewPublic]:
        """List public submitted reviews; private drafts are never included."""
        pull = await self._pull(owner, repo, number)
        reviews = await self.store.list_reviews(pull.id)
        if not reviews:
            return []
        base, head = await self.repository_service.branch_heads(owner, repo, pull.base_branch, pull.head_branch)
        return [
            self._public(review).model_copy(
                update={
                    "outdated": (review.base_commit != base or review.head_commit != head) if base and head else None
                }
            )
            for review in reviews
        ]

    async def _review(self, owner: str, repo: str, number: int, review_id: uuid.UUID) -> PullRequestReview:
        pull = await self._pull(owner, repo, number)
        review = await self.store.get_review(pull.id, review_id)
        if review is None:
            raise HTTPException(status_code=404, detail="Review not found")
        return review

    async def get_comment_context(
        self, owner: str, repo: str, number: int, review_id: uuid.UUID, index: int
    ) -> DiffHunk:
        """Serve legacy comments without sending the entire highlighted file to the browser."""
        review = await self._review(owner, repo, number, review_id)
        if index >= len(review.comments):
            raise HTTPException(status_code=404, detail="Review comment not found")
        comment = ReviewCommentPublic.model_validate(review.comments[index])
        if comment.context is not None:
            return comment.context
        return await self.repository_service.get_diff_context(
            owner, repo, review.base_commit, review.head_commit, comment.path, comment.side, comment.line
        )

    async def reply(
        self, owner: str, repo: str, number: int, review_id: uuid.UUID, body: ReviewReplyCreate, user: User
    ) -> ReviewReplyPublic:
        """Publish a reply on its original thread, including after merging or new pushes."""
        review = await self._review(owner, repo, number, review_id)
        if not body.body.strip():
            raise HTTPException(status_code=422, detail="Add a reply before submitting")
        if body.comment_index is not None and body.comment_index >= len(review.comments):
            raise HTTPException(status_code=404, detail="Review comment not found")
        if body.comment_index is None and not review.body.strip():
            raise HTTPException(status_code=422, detail="This review has no overall comment to reply to")
        reply = PullRequestReviewReply(
            review_id=review.id,
            author_id=user.id,
            author=user,
            comment_index=body.comment_index,
            body=body.body.strip(),
        )
        await self.store.add_reply(reply)
        return self._reply_public(reply)

    async def get_workspace(self, owner: str, repo: str, number: int, user: User) -> ReviewWorkspacePublic:
        """Read the current user's draft and comparison-scoped viewed files."""
        pull = await self._pull(owner, repo, number)
        comparison = await self._comparison(owner, repo, pull)
        return self._workspace_public(await self.store.workspace(pull.id, user.id), comparison)

    async def save_draft(
        self, owner: str, repo: str, number: int, body: ReviewDraft, user: User
    ) -> ReviewWorkspacePublic:
        """Save line comments privately until the review is submitted."""
        pull = await self._pull(owner, repo, number)
        comparison = await self._comparison(owner, repo, pull)
        self._validate_revision(body, comparison)
        await self._validate_comments(owner, repo, body.comments, comparison)
        workspace = await self.store.workspace(pull.id, user.id, for_update=True)
        workspace.draft = body.model_dump(mode="json")
        await self.store.save_workspace(workspace)
        return self._workspace_public(workspace, comparison)

    async def mark_reviewed(
        self, owner: str, repo: str, number: int, body: ReviewedFileUpdate, user: User
    ) -> ReviewWorkspacePublic:
        """Persist viewed status for a file at the displayed revisions."""
        pull = await self._pull(owner, repo, number)
        comparison = await self._comparison(owner, repo, pull)
        self._validate_revision(body, comparison)
        if body.path not in {file.path for file in comparison.files}:
            raise HTTPException(status_code=422, detail="File is not in this comparison")
        workspace = await self.store.workspace(pull.id, user.id, for_update=True)
        current = self._workspace_public(workspace, comparison)
        paths = set(current.reviewed_paths)
        (paths.add if body.reviewed else paths.discard)(body.path)
        workspace.reviewed_paths = sorted(paths)
        workspace.base_commit, workspace.head_commit = body.base_commit, body.head_commit
        await self.store.save_workspace(workspace)
        return self._workspace_public(workspace, comparison)

    async def submit(self, owner: str, repo: str, number: int, body: ReviewSubmit, user: User) -> ReviewPublic:
        """Submit an immutable review and its comments as a single operation."""
        pull = await self._pull(owner, repo, number)
        if body.state == ReviewState.APPROVED and pull.author_id == user.id:
            raise HTTPException(status_code=403, detail="You cannot approve your own pull request")
        if pull.state != IssueState.OPEN:
            raise HTTPException(status_code=409, detail="Only open pull requests can be reviewed")
        comparison = await self._comparison(owner, repo, pull)
        self._validate_revision(body, comparison)
        files = await self._validate_comments(owner, repo, body.comments, comparison)
        if body.state != ReviewState.APPROVED and not body.body.strip() and not body.comments:
            raise HTTPException(status_code=422, detail="Add an overall comment or a line comment before submitting")
        review = PullRequestReview(
            pull_request_id=pull.id,
            author_id=user.id,
            author=user,
            state=body.state.value,
            body=body.body.strip(),
            comments=[
                {
                    **comment.model_dump(),
                    "context": context.model_dump(mode="json")
                    if (context := comment_context(files[comment.path].hunks, comment.side, comment.line)) is not None
                    else None,
                }
                for comment in body.comments
            ],
            replies=[],
            base_commit=body.base_commit,
            head_commit=body.head_commit,
        )
        workspace = await self.store.workspace(pull.id, user.id, for_update=True)
        await self.store.submit(review, workspace)
        return self._public(review)
