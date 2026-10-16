import { Check, Diff, GitMerge, MessageSquare } from "lucide-react"

type ReviewStatus = "approved" | "changes_requested" | "comment" | "merged"
const icons = { approved: Check, changes_requested: Diff, comment: MessageSquare, merged: GitMerge }
const labels = {
  approved: "Approved",
  changes_requested: "Changes requested",
  comment: "Reviewed with comments",
  merged: "Merged",
}
const tones = {
  approved: "bg-success text-success-foreground",
  changes_requested: "bg-destructive text-destructive-foreground",
  comment: "bg-secondary text-muted-foreground",
  merged: "bg-merged text-merged-foreground",
}
const inlineTones = {
  approved: "text-success",
  changes_requested: "text-destructive",
  comment: "text-muted-foreground",
  merged: "text-merged",
}

export const ReviewStatusIcon = ({ state, inline = false }: { state: ReviewStatus; inline?: boolean }) => {
  const Icon = icons[state]
  return (
    <Icon
      role="img"
      aria-label={labels[state]}
      data-review-state={state}
      className={
        inline ? `size-4 shrink-0 ${inlineTones[state]}` : `size-8 shrink-0 rounded-full p-1.5 ${tones[state]}`
      }
    />
  )
}
