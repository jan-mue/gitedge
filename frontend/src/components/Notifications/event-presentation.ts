import type { ActivityKind, NotificationPublic } from "@/client"

const events: Record<ActivityKind, { label: string; description: string }> = {
  workflow_failed: { label: "Workflow failed", description: "A workflow you follow failed" },
  star: { label: "Starred", description: "Starred this repository" },
  watch: { label: "Watching", description: "Started watching this repository" },
  fork: { label: "Forked", description: "Forked this repository" },
  issue_open: { label: "Opened", description: "Opened this issue" },
  issue_close: { label: "Closed", description: "Closed this issue" },
  issue_reopen: { label: "Reopened", description: "Reopened this issue" },
  issue_edit: { label: "Edited", description: "Updated this issue" },
  pull_request_open: { label: "Opened", description: "Opened this pull request" },
  pull_request_close: { label: "Closed", description: "Closed this pull request" },
  pull_request_reopen: { label: "Reopened", description: "Reopened this pull request" },
  pull_request_edit: { label: "Edited", description: "Updated this pull request" },
  pull_request_merge: { label: "Merged", description: "Merged this pull request" },
  comment: { label: "Commented", description: "Added a comment to this discussion" },
  comment_edit: { label: "Comment edited", description: "Edited a comment in this discussion" },
  reaction: { label: "Reaction", description: "Reacted to a comment in this discussion" },
  release: { label: "Published", description: "Published this release" },
}

export const notificationEvent = (notification: NotificationPublic) => {
  return events[notification.kind]
}
