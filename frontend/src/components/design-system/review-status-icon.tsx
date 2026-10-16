import { Check, Diff, GitMerge, GitPullRequest, GitPullRequestClosed, MessageSquare } from "lucide-react"

type ReviewStatus = "approved" | "changes_requested" | "comment" | "merged" | "closed" | "reopened"
const icons = {
  approved: Check,
  changes_requested: Diff,
  comment: MessageSquare,
  merged: GitMerge,
  closed: GitPullRequestClosed,
  reopened: GitPullRequest,
}
const labels = {
  approved: "Approved",
  changes_requested: "Changes requested",
  comment: "Reviewed with comments",
  merged: "Merged",
  closed: "Closed",
  reopened: "Reopened",
}
const tones = {
  approved: "bg-success text-success-foreground",
  changes_requested: "bg-destructive text-destructive-foreground",
  comment: "bg-secondary text-muted-foreground",
  merged: "bg-merged text-merged-foreground",
  closed: "bg-destructive text-destructive-foreground",
  reopened: "bg-success text-success-foreground",
}
const inlineTones = {
  approved: "text-success",
  changes_requested: "text-destructive",
  comment: "text-muted-foreground",
  merged: "text-merged",
  closed: "text-destructive",
  reopened: "text-success",
}

export const ReviewStatusIcon = ({ state, inline = false }: { state: ReviewStatus; inline?: boolean }) => {
  const Icon = icons[state]
  return (
    <span
      role="img"
      aria-label={labels[state]}
      data-review-state={state}
      className={
        inline
          ? `inline-flex size-4 shrink-0 items-center justify-center ${inlineTones[state]}`
          : `inline-flex size-8 shrink-0 items-center justify-center rounded-full ${tones[state]}`
      }
    >
      <Icon className="size-4 shrink-0" aria-hidden="true" />
    </span>
  )
}
