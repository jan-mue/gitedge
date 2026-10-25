import { useQuery } from "@tanstack/react-query"
import { useEffect, useRef, useState } from "react"
import type { DiffHunk, ReviewCommentPublic, ReviewPublic } from "@/client"
import { reviewsGetCommentContextOptions } from "@/client/@tanstack/react-query.gen"
import { Button, CodeSkeleton, ConversationCard, ExternalLink, MarkdownContent } from "@/components/design-system"
import { DiffCodeRow } from "./DiffCodeRow"
import { ReviewReplies } from "./ReviewReplies"
import "./diff-viewer.css"

const contextLines = (context: DiffHunk | null | undefined, comment: ReviewCommentPublic) => {
  const anchor =
    context?.lines.findIndex((line) => (comment.side === "old" ? line.old_line : line.new_line) === comment.line) ?? -1
  return anchor >= 0 ? context?.lines.slice(Math.max(0, anchor - 3), anchor + 1) : undefined
}

export const ReviewDiffComment = ({
  owner,
  repo,
  number,
  review,
  comment,
  commentIndex,
  outdated,
  username,
}: {
  owner: string
  repo: string
  number: number
  review: ReviewPublic
  comment: ReviewCommentPublic
  commentIndex: number
  outdated: boolean
  username?: string
}) => {
  const ref = useRef<HTMLElement>(null)
  const [visible, setVisible] = useState(false)
  useEffect(() => {
    if (comment.context || !ref.current) return
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true)
          observer.disconnect()
        }
      },
      { rootMargin: "100px" },
    )
    observer.observe(ref.current)
    return () => observer.disconnect()
  }, [comment.context])
  const { data, isError, refetch } = useQuery({
    ...reviewsGetCommentContextOptions({
      path: { owner, repo, number, review_id: review.id, comment_index: commentIndex },
    }),
    enabled: !comment.context && visible,
    staleTime: Infinity,
  })
  const context = comment.context ?? data
  const lines = contextLines(context, comment)
  const revision = comment.side === "old" ? review.base_commit : review.head_commit
  const renderDiffContext = () =>
    isError ? (
      <p role="alert" className="p-3 font-sans text-sm">
        Unable to load diff context.{" "}
        <Button variant="text" size="text" onClick={() => refetch()}>
          Retry
        </Button>
      </p>
    ) : !context ? (
      <CodeSkeleton lineCount={4} />
    ) : lines?.length ? (
      <>
        <div className="diff-hunk">{context.header}</div>
        {lines.map((line, index) => (
          <div
            key={index}
            className="diff-cell"
            data-kind={line.kind}
            data-comment-anchor={index === lines.length - 1 ? "true" : undefined}
          >
            <DiffCodeRow line={line} />
          </div>
        ))}
      </>
    ) : (
      <p className="p-3 font-sans text-sm text-muted-foreground">Diff context is unavailable for this line.</p>
    )

  return (
    <section
      ref={ref}
      className="diff-viewer min-w-0 overflow-hidden rounded-lg border border-border bg-card"
      aria-label={`Review comment on ${comment.path} ${comment.side} line ${comment.line}`}
    >
      <header className="flex flex-wrap items-center gap-2 border-b border-border bg-secondary px-3 py-2 text-xs">
        <span className="min-w-0 break-all font-mono">
          <ExternalLink
            appearance="muted"
            href={`/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/src/commit/${revision}/${comment.path.split("/").map(encodeURIComponent).join("/")}`}
          >
            {comment.path}
          </ExternalLink>
        </span>
        {outdated && <span className="rounded bg-muted px-1.5 py-0.5 text-muted-foreground">Outdated</span>}
        <span className="ml-auto text-muted-foreground">
          {comment.side === "old" ? "Original" : "Changed"} line {comment.line}
        </span>
      </header>
      <section className="review-diff-context diff-scroll border-b border-border" aria-label="Diff context">
        {renderDiffContext()}
      </section>
      <ConversationCard author={review.author_username} date={review.created_at} badge="Reviewer" embedded thread>
        {comment.body_html ? (
          <MarkdownContent html={comment.body_html} />
        ) : (
          <p className="whitespace-pre-wrap">{comment.body}</p>
        )}
      </ConversationCard>
      <ReviewReplies
        owner={owner}
        repo={repo}
        number={number}
        review={review}
        commentIndex={commentIndex}
        username={username}
      />
    </section>
  )
}
