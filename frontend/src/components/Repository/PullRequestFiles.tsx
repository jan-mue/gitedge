import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { ChevronDown, MessageSquare, ShieldCheck, X } from "lucide-react"
import { useState } from "react"
import type { CompareResult, ReviewDraft, ReviewLineComment, ReviewPublic, ReviewState } from "@/client"
import {
  reviewsGetWorkspaceOptions,
  reviewsGetWorkspaceQueryKey,
  reviewsListReviewsQueryKey,
  reviewsMarkReviewedMutation,
  reviewsSaveDraftMutation,
  reviewsSubmitReviewMutation,
} from "@/client/@tanstack/react-query.gen"
import {
  Button,
  ConversationCard,
  Popover,
  PopoverClose,
  PopoverContent,
  PopoverTrigger,
  Textarea,
} from "@/components/design-system"
import { type DiffAnnotation, DiffViewer } from "@/components/Repository/DiffViewer"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"
import { ReviewDiffComment } from "./ReviewDiffComment"
import { ReviewReplies } from "./ReviewReplies"

interface PullRequestFilesProps {
  owner: string
  repo: string
  number: number
  changes: CompareResult
  reviews: ReviewPublic[]
  username?: string
  author: string
  isOpen: boolean
}

export const PullRequestFiles = ({
  owner,
  repo,
  number,
  changes,
  reviews,
  username,
  author,
  isOpen,
}: PullRequestFilesProps) => {
  const path = { owner, repo, number }
  const queryClient = useQueryClient()
  const { showErrorToast, showSuccessToast } = useCustomToast()
  const [reviewOpen, setReviewOpen] = useState(false)
  const [reviewBody, setReviewBody] = useState("")
  const [reviewBodyTouched, setReviewBodyTouched] = useState(false)
  const {
    data: workspace,
    isPending,
    isError,
    refetch,
  } = useQuery({ ...reviewsGetWorkspaceOptions({ path }), enabled: !!username })
  const draft = workspace?.draft
  const stale = !!draft && (draft.base_commit !== changes.base_commit || draft.head_commit !== changes.head_commit)
  const canReview = !!username && !!workspace && isOpen && !!changes.base_commit && !!changes.head_commit && !stale
  const draftBody = (comments: ReviewLineComment[], body = draft?.body ?? ""): ReviewDraft => ({
    base_commit: changes.base_commit!,
    head_commit: changes.head_commit!,
    body,
    comments,
  })
  const saveDraft = useMutation({
    ...reviewsSaveDraftMutation(),
    onSuccess: (data) => queryClient.setQueryData(reviewsGetWorkspaceQueryKey({ path }), data),
    onError: handleError.bind(showErrorToast),
  })
  const markReviewed = useMutation({
    ...reviewsMarkReviewedMutation(),
    onSuccess: (data) => queryClient.setQueryData(reviewsGetWorkspaceQueryKey({ path }), data),
    onError: handleError.bind(showErrorToast),
  })
  const submitReview = useMutation({
    ...reviewsSubmitReviewMutation(),
    onSuccess: async () => {
      setReviewOpen(false)
      setReviewBody("")
      setReviewBodyTouched(false)
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: reviewsGetWorkspaceQueryKey({ path }) }),
        queryClient.invalidateQueries({ queryKey: reviewsListReviewsQueryKey({ path }) }),
      ])
      showSuccessToast("Review submitted")
    },
    onError: handleError.bind(showErrorToast),
  })
  const comments = stale ? [] : (draft?.comments ?? [])
  const annotations: DiffAnnotation[] = reviews
    .filter((review) => review.base_commit === changes.base_commit && review.head_commit === changes.head_commit)
    .flatMap((review) =>
      (review.comments ?? []).map((comment, index) => ({
        ...comment,
        id: `${review.id}-${index}`,
        author: review.author_username,
      })),
    )
  annotations.push(
    ...comments.map((comment, index) => ({
      ...comment,
      id: `draft-${index}`,
      author: username ?? "You",
      pending: true,
    })),
  )
  const busy = saveDraft.isPending || submitReview.isPending || markReviewed.isPending
  const submit = (state: ReviewState) =>
    submitReview.mutate({ path, body: { ...draftBody(comments, reviewBody), state } })

  return (
    <div
      className="space-y-3"
      data-testid="pr-files"
      data-head-revision={changes.head_commit}
      data-draft-head={draft?.head_commit}
    >
      {!username && (
        <p className="text-sm text-muted-foreground">
          Sign in to add line comments, mark files as viewed, and submit a review.
        </p>
      )}
      {username && isPending && <p className="text-sm text-muted-foreground">Loading your review…</p>}
      {username && isError && (
        <div className="flex items-center gap-3 text-sm text-destructive">
          Unable to load your review.
          <Button variant="repository" size="compact" onClick={() => refetch()}>
            Retry
          </Button>
        </div>
      )}
      {stale && (
        <div className="rounded-lg border border-warning/40 bg-warning/5 p-4 text-sm">
          <p className="font-medium">The branches changed since you started this review.</p>
          <p className="mt-1 text-muted-foreground">
            Your earlier draft is saved below. Start a new draft to comment on the current diff.
          </p>
          <details className="my-3">
            <summary>Earlier draft ({draft?.comments?.length ?? 0} line comments)</summary>
            <p className="mt-2 whitespace-pre-wrap">{draft?.body}</p>
            {draft?.comments?.map((comment, index) => (
              <p className="mt-2 whitespace-pre-wrap" key={index}>
                <strong>
                  {comment.path}:{comment.line} ({comment.side})
                </strong>
                {"\n"}
                {comment.body}
              </p>
            ))}
          </details>
          <Button
            variant="repository"
            size="compact"
            disabled={busy}
            onClick={() => saveDraft.mutate({ path, body: draftBody([], draft?.body ?? "") })}
          >
            Start review of current changes
          </Button>
        </div>
      )}
      <DiffViewer
        diffSource={{ owner, repo, base: changes.base_commit ?? "", head: changes.head_commit ?? "" }}
        files={changes.files}
        additions={changes.additions}
        deletions={changes.deletions}
        annotations={annotations}
        reviewedPaths={workspace?.reviewed_paths ?? []}
        reviewBusy={busy}
        onReviewed={
          username && workspace && changes.base_commit && changes.head_commit
            ? (filePath, reviewed) =>
                markReviewed.mutate({
                  path,
                  body: {
                    base_commit: changes.base_commit!,
                    head_commit: changes.head_commit!,
                    path: filePath,
                    reviewed,
                  },
                })
            : undefined
        }
        onAddComment={
          canReview
            ? async (comment) => {
                await saveDraft.mutateAsync({ path, body: draftBody([...comments, comment]) })
              }
            : undefined
        }
        onDeleteComment={
          canReview && !busy
            ? (id) =>
                saveDraft.mutate({ path, body: draftBody(comments.filter((_, index) => `draft-${index}` !== id)) })
            : undefined
        }
        toolbar={
          <Popover
            open={reviewOpen}
            onOpenChange={(open) => {
              if (!open && submitReview.isPending) return
              if (!open && reviewBody !== (draft?.body ?? ""))
                saveDraft.mutate({ path, body: draftBody(comments, reviewBody) })
              setReviewOpen(open)
            }}
          >
            <PopoverTrigger asChild>
              <Button
                size="compact"
                disabled={!canReview}
                aria-disabled={busy}
                onClick={(event) => {
                  if (busy) {
                    event.preventDefault()
                    return
                  }
                  if (!reviewBodyTouched) setReviewBody(draft?.body ?? "")
                  setReviewOpen(true)
                }}
              >
                <MessageSquare className="size-4" />
                Review{comments.length > 0 && ` (${comments.length})`}
                <ChevronDown className="size-3" />
              </Button>
            </PopoverTrigger>
            <PopoverContent appearance="review" aria-label="Submit review">
              <div className="mb-4 space-y-2">
                <div className="flex items-center justify-between">
                  <h2 className="font-medium">Submit review</h2>
                  <PopoverClose asChild>
                    <Button variant="ghost" size="icon-xs" aria-label="Close review">
                      <X className="size-4" />
                    </Button>
                  </PopoverClose>
                </div>
                <p className="text-xs text-muted-foreground">
                  {comments.length} pending line {comments.length === 1 ? "comment" : "comments"}. Add an overall
                  comment and choose your review outcome.
                </p>
              </div>
              <Textarea
                aria-label="Review comment"
                placeholder="Leave an overall review comment…"
                rows={6}
                maxLength={20000}
                value={reviewBody}
                onChange={(event) => {
                  setReviewBody(event.target.value)
                  setReviewBodyTouched(true)
                }}
              />
              {username === author && (
                <p className="text-xs text-muted-foreground">You cannot approve your own pull request.</p>
              )}
              <div className="mt-4 flex flex-wrap gap-2">
                <Button
                  size="compact"
                  variant="success"
                  disabled={username === author || busy}
                  onClick={() => submit("approved")}
                >
                  <ShieldCheck className="size-4" />
                  Approve
                </Button>
                <Button
                  size="compact"
                  variant="repository"
                  disabled={busy || (!reviewBody.trim() && !comments.length)}
                  onClick={() => submit("comment")}
                >
                  Comment
                </Button>
                <Button
                  size="compact"
                  variant="destructive"
                  disabled={busy || (!reviewBody.trim() && !comments.length)}
                  onClick={() => submit("changes_requested")}
                >
                  Request changes
                </Button>
                <Button
                  size="compact"
                  variant="ghost"
                  disabled={busy}
                  onClick={() =>
                    saveDraft.mutate(
                      { path, body: draftBody(comments, reviewBody) },
                      { onSuccess: () => setReviewOpen(false) },
                    )
                  }
                >
                  Save draft
                </Button>
              </div>
            </PopoverContent>
          </Popover>
        }
      />
    </div>
  )
}

const stateLabel = {
  approved: "approved these changes",
  comment: "reviewed with comments",
  changes_requested: "requested changes",
}

export const ReviewTimeline = ({
  owner,
  repo,
  reviews,
  changes,
  number,
  username,
}: {
  owner: string
  repo: string
  reviews: ReviewPublic[]
  changes?: CompareResult
  number: number
  username?: string
}) => (
  <div className="space-y-4">
    {reviews.map((review) => (
      <div key={review.id} data-testid={`review-${review.id}`} className="space-y-4">
        <div className="flex flex-wrap items-center gap-x-1.5 gap-y-1 py-1 text-sm text-muted-foreground">
          <strong className="font-medium text-foreground">{review.author_username}</strong>
          <span>{stateLabel[review.state]}</span>
          <time dateTime={review.created_at}>{new Date(review.created_at).toLocaleString()}</time>
        </div>
        {(review.outdated ??
          (changes && (review.head_commit !== changes.head_commit || review.base_commit !== changes.base_commit))) && (
          <p className="text-xs text-muted-foreground">
            Review of an earlier revision · {review.head_commit.slice(0, 10)}
          </p>
        )}
        {review.body && (
          <section className="overflow-hidden rounded-lg border border-border" aria-label="Review comment">
            <ConversationCard author={review.author_username} date={review.created_at} badge="Reviewer" embedded>
              <p className="whitespace-pre-wrap text-sm">{review.body}</p>
            </ConversationCard>
            <ReviewReplies owner={owner} repo={repo} number={number} review={review} username={username} />
          </section>
        )}
        {(review.comments ?? []).map((comment, index) => (
          <ReviewDiffComment
            key={index}
            owner={owner}
            repo={repo}
            review={review}
            comment={comment}
            number={number}
            commentIndex={index}
            username={username}
            outdated={
              review.outdated ??
              (!!changes && (review.head_commit !== changes.head_commit || review.base_commit !== changes.base_commit))
            }
          />
        ))}
      </div>
    ))}
  </div>
)
