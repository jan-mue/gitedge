"""Pull request review validation and lifecycle."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException

from app.entities.comments import Comment
from app.entities.issues import IssueState
from app.entities.reviews import DiffSide, PullRequestComment, PullRequestReview
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
            owner,
            repo,
            pull.merge_base or pull.base_branch,
            pull.merged_head_commit or pull.head_branch,
            include_diff=False,
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
        indices = {link.comment.id: index for index, link in enumerate(review.line_comments)}
        replies = [
            ReviewService._reply_public(reply, indices.get(link.comment.id))
            for link in review.comments
            for reply in link.comment.replies
        ]
        replies.sort(key=lambda reply: (reply.created_at, reply.id))
        return ReviewPublic(
            id=review.id,
            author_username=review.author.name,
            created_at=review.created_at,
            state=ReviewState(review.state),
            body=review.body,
            body_html=render_markdown(review.body),
            summary_comment_id=review.summary.id if review.summary else None,
            base_commit=review.base_commit,
            head_commit=review.head_commit,
            comments=[ReviewService._comment_public(link) for link in review.line_comments],
            replies=replies,
        )

    @staticmethod
    def _comment_public(link: PullRequestComment) -> ReviewCommentPublic:
        return ReviewCommentPublic(
            id=link.comment.id,
            path=link.path or "",
            side="old" if link.side == DiffSide.OLD else "new",
            line=link.line or 1,
            body=link.comment.body,
            body_html=render_markdown(link.comment.body),
            context=link.context,
        )

    @staticmethod
    def _reply_public(reply: Comment, comment_index: int | None) -> ReviewReplyPublic:
        return ReviewReplyPublic(
            id=reply.id,
            author_username=reply.author.name,
            created_at=reply.created_at,
            comment_index=comment_index,
            reply_to=reply.reply_to,
            body=reply.body,
            body_html=render_markdown(reply.body),
        )

    async def list_reviews(self, owner: str, repo: str, number: int) -> list[ReviewPublic]:
        """List public submitted reviews; private drafts are never included."""
        pull = await self._pull(owner, repo, number)
        reviews = await self.store.list_reviews(pull.id)
        if not reviews:
            return []
        if pull.merged_head_commit and pull.merge_base:
            base, head = pull.merge_base, pull.merged_head_commit
        else:
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
        if index >= len(review.line_comments):
            raise HTTPException(status_code=404, detail="Review comment not found")
        comment = self._comment_public(review.line_comments[index])
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
        parent = None
        index = body.comment_index
        if body.reply_to is not None:
            link = next((link for link in review.comments if link.comment.id == body.reply_to), None)
            if link is None:
                raise HTTPException(status_code=404, detail="Review comment not found")
            parent = link.comment
            index = review.line_comments.index(link) if link.path is not None else None
        elif index is not None:
            if index >= len(review.line_comments):
                raise HTTPException(status_code=404, detail="Review comment not found")
            parent = review.line_comments[index].comment
        else:
            parent = review.summary
        if parent is None:
            raise HTTPException(status_code=422, detail="This review has no overall comment to reply to")
        reply = Comment(
            issue_id=review.pull_request_id,
            author_id=user.id,
            author=user,
            reply_to=parent.id,
            parent=parent,
            body=body.body.strip(),
        )
        await self.store.add_reply(reply)
        return self._reply_public(reply, index)

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
            state=body.state,
            comments=[],
            base_commit=body.base_commit,
            head_commit=body.head_commit,
        )

        def comment(text: str) -> Comment:
            return Comment(issue_id=pull.id, author_id=user.id, author=user, body=text.strip(), replies=[])

        if body.body.strip():
            review.comments.append(PullRequestComment(position=-1, comment=comment(body.body)))
        for index, line_comment in enumerate(body.comments):
            context = comment_context(files[line_comment.path].hunks, line_comment.side, line_comment.line)
            review.comments.append(
                PullRequestComment(
                    position=index,
                    comment=comment(line_comment.body),
                    path=line_comment.path,
                    side=DiffSide(line_comment.side),
                    line=line_comment.line,
                    context=context.model_dump(mode="json") if context is not None else None,
                )
            )
        workspace = await self.store.workspace(pull.id, user.id, for_update=True)
        await self.store.submit(review, workspace)
        return self._public(review)
