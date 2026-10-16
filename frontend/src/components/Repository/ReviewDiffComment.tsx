import { useQuery } from "@tanstack/react-query"
import { useEffect, useRef, useState } from "react"
import type { ReviewLineComment, ReviewPublic } from "@/client"
import { repositoriesGetDiffFileOptions } from "@/client/@tanstack/react-query.gen"
import { Button, CodeSkeleton, ConversationCard, ExternalLink } from "@/components/design-system"
import { DiffCodeRow } from "./DiffCodeRow"
import "./diff-viewer.css"

export const ReviewDiffComment = ({
  owner,
  repo,
  review,
  comment,
  outdated,
}: {
  owner: string
  repo: string
  review: ReviewPublic
  comment: ReviewLineComment
  outdated: boolean
}) => {
  const ref = useRef<HTMLElement>(null)
  const [visible, setVisible] = useState(false)
  useEffect(() => {
    if (!ref.current) return
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true)
          observer.disconnect()
        }
      },
      { rootMargin: "400px" },
    )
    observer.observe(ref.current)
    return () => observer.disconnect()
  }, [])
  const {
    data: file,
    isError,
    refetch,
  } = useQuery({
    ...repositoriesGetDiffFileOptions({
      path: { owner, repo },
      query: { base: review.base_commit, head: review.head_commit, file_path: comment.path },
    }),
    enabled: visible,
    staleTime: Infinity,
  })
  const hunk = file?.hunks?.find((hunk) =>
    hunk.lines.some((line) => (comment.side === "old" ? line.old_line : line.new_line) === comment.line),
  )
  const anchor =
    hunk?.lines.findIndex((line) => (comment.side === "old" ? line.old_line : line.new_line) === comment.line) ?? -1
  const lines = hunk?.lines.slice(Math.max(0, anchor - 3), anchor + 3)
  const revision = comment.side === "old" ? review.base_commit : review.head_commit
  const path = comment.side === "old" ? file?.old_path || comment.path : comment.path
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
            href={`/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/src/commit/${revision}/${path.split("/").map(encodeURIComponent).join("/")}`}
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
        {isError ? (
          <p role="alert" className="p-3 font-sans text-sm">
            Unable to load diff context.{" "}
            <Button variant="text" size="text" onClick={() => refetch()}>
              Retry
            </Button>
          </p>
        ) : !file ? (
          <CodeSkeleton lineCount={4} />
        ) : hunk && lines?.length ? (
          <>
            <div className="diff-hunk">{hunk.header}</div>
            {lines.map((line, index) => (
              <div
                key={index}
                className="diff-cell"
                data-kind={line.kind}
                data-comment-anchor={
                  (comment.side === "old" ? line.old_line : line.new_line) === comment.line ? "true" : undefined
                }
              >
                <DiffCodeRow line={line} />
              </div>
            ))}
          </>
        ) : (
          <p className="p-3 font-sans text-sm text-muted-foreground">Diff context is unavailable for this line.</p>
        )}
      </section>
      <ConversationCard author={review.author_username} date={review.created_at} badge="Reviewer" embedded>
        <p className="whitespace-pre-wrap">{comment.body}</p>
      </ConversationCard>
    </section>
  )
}
