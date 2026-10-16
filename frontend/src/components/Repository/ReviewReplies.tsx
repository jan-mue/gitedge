import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Reply } from "lucide-react"
import { useState } from "react"
import type { ReviewPublic } from "@/client"
import { reviewsListReviewsQueryKey, reviewsReplyToReviewMutation } from "@/client/@tanstack/react-query.gen"
import { Button, ConversationCard, ExternalLink, MarkdownComposer, MarkdownContent } from "@/components/design-system"

export const ReviewReplies = ({
  owner,
  repo,
  number,
  review,
  commentIndex = null,
  username,
}: {
  owner: string
  repo: string
  number: number
  review: ReviewPublic
  commentIndex?: number | null
  username?: string
}) => {
  const client = useQueryClient()
  const [open, setOpen] = useState(false)
  const [body, setBody] = useState("")
  const mutation = useMutation({
    ...reviewsReplyToReviewMutation(),
    onSuccess: (reply) => {
      client.setQueryData<ReviewPublic[]>(reviewsListReviewsQueryKey({ path: { owner, repo, number } }), (reviews) =>
        reviews?.map((item) => (item.id === review.id ? { ...item, replies: [...(item.replies ?? []), reply] } : item)),
      )
      setBody("")
      setOpen(false)
      return client.invalidateQueries({ queryKey: reviewsListReviewsQueryKey({ path: { owner, repo, number } }) })
    },
  })
  return (
    <fieldset className="min-w-0 border-t border-border" aria-label="Review replies">
      {(review.replies ?? [])
        .filter((reply) => (reply.comment_index ?? null) === commentIndex)
        .map((reply) => (
          <div key={reply.id} className="border-b border-border" data-testid={`review-reply-${reply.id}`}>
            <ConversationCard author={reply.author_username} date={reply.created_at} embedded>
              <MarkdownContent html={reply.body_html} />
            </ConversationCard>
          </div>
        ))}
      {open ? (
        <div className="space-y-2 p-3">
          {mutation.isError && (
            <p role="alert" className="text-sm text-destructive">
              Unable to post your reply. Try again.
            </p>
          )}
          <MarkdownComposer
            value={body}
            onChange={setBody}
            label="Reply to review comment"
            actions={
              <>
                <Button
                  variant="repository"
                  size="compact"
                  disabled={mutation.isPending}
                  onClick={() => setOpen(false)}
                >
                  Cancel
                </Button>
                <Button
                  size="compact"
                  disabled={!body.trim() || mutation.isPending}
                  onClick={() =>
                    mutation.mutate({
                      path: { owner, repo, number, review_id: review.id },
                      body: { body: body.trim(), comment_index: commentIndex },
                    })
                  }
                >
                  <Reply className="size-3.5" />
                  {mutation.isPending ? "Replying…" : "Reply"}
                </Button>
              </>
            }
          />
        </div>
      ) : (
        <div className="flex justify-end bg-secondary/30 px-3 py-2">
          {username ? (
            <Button size="compact" variant="repository" onClick={() => setOpen(true)}>
              <Reply className="size-3.5" /> Reply
            </Button>
          ) : (
            <ExternalLink href="/login" appearance="caption">
              Sign in to reply
            </ExternalLink>
          )}
        </div>
      )}
    </fieldset>
  )
}
