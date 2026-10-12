import { CircleDot, GitMerge, GitPullRequest, MessageSquare, MoreHorizontal } from "lucide-react"
import { type ComponentProps, useState } from "react"
import type { ActivityPublic } from "@/client"
import {
  Button,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  Link,
  type LinkAppearance,
} from "@/components/design-system"
import { useCopyToClipboard } from "@/hooks/useCopyToClipboard"
import useCustomToast from "@/hooks/useCustomToast"

export const activityActions: Record<string, string> = {
  star: "starred",
  watch: "started watching",
  fork: "forked",
  issue_open: "opened issue",
  issue_close: "closed issue",
  issue_reopen: "reopened issue",
  comment: "commented on",
  pull_request_open: "opened pull request",
  pull_request_merge: "merged pull request",
  pull_request_close: "closed pull request",
  pull_request_reopen: "reopened pull request",
  release: "published release",
}

const relativeTime = new Intl.RelativeTimeFormat("en", { numeric: "auto" })
const formatTime = (date: string) => {
  const seconds = Math.max(0, (Date.now() - new Date(date).getTime()) / 1000)
  if (seconds < 60) return "just now"
  if (seconds < 3600) return relativeTime.format(-Math.floor(seconds / 60), "minute")
  if (seconds < 86400) return relativeTime.format(-Math.floor(seconds / 3600), "hour")
  if (seconds < 604800) return relativeTime.format(-Math.floor(seconds / 86400), "day")
  return new Date(date).toLocaleDateString()
}

const TargetLink = ({
  activity,
  ...props
}: Omit<ComponentProps<"a">, "className" | "style"> & {
  activity: ActivityPublic
  appearance?: LinkAppearance
}) => {
  const owner = activity.repo_owner
  const repo = activity.repo_name
  if (!owner || !repo) return <span>{props.children}</span>
  if (activity.target_number != null && activity.target_type === "pull_request")
    return (
      <Link
        {...props}
        to="/$owner/$repo/pulls/$number"
        params={{ owner, repo, number: String(activity.target_number) }}
      />
    )
  if (activity.target_number != null && activity.target_type === "issue")
    return (
      <Link
        {...props}
        to="/$owner/$repo/issues/$number"
        params={{ owner, repo, number: String(activity.target_number) }}
      />
    )
  if (activity.target_type === "release")
    return <Link {...props} to="/$owner/$repo/releases" params={{ owner, repo }} />
  return <Link {...props} to="/$owner/$repo" params={{ owner, repo }} />
}

const inlineText = (text: string) =>
  text.split(/(`[^`]+`|\*\*[^*]+\*\*)/g).map((part, index) =>
    part.startsWith("`") && part.endsWith("`") ? (
      <code key={index} className="rounded bg-accent px-1 py-0.5 font-mono text-xs">
        {part.slice(1, -1)}
      </code>
    ) : part.startsWith("**") && part.endsWith("**") ? (
      <strong key={index}>{part.slice(2, -2)}</strong>
    ) : (
      part
    ),
  )
const Description = ({ text }: { text: string }) => (
  <div className="space-y-1 whitespace-pre-wrap break-words text-sm leading-relaxed [overflow-wrap:anywhere]">
    {text.split("\n").map((line, index) => {
      if (/^#{1,6} /.test(line))
        return (
          <p key={index} className="pt-1 font-semibold">
            {inlineText(line.replace(/^#{1,6} /, ""))}
          </p>
        )
      if (/^[-*] /.test(line))
        return (
          <p key={index} className="pl-3">
            • {inlineText(line.slice(2))}
          </p>
        )
      return line.trim() ? <p key={index}>{inlineText(line)}</p> : <div key={index} className="h-2" />
    })}
  </div>
)

const ActivityCard = ({ activity }: { activity: ActivityPublic }) => {
  const [expanded, setExpanded] = useState(false)
  const [, copy] = useCopyToClipboard()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const body = activity.preview?.body ?? ""
  const isLong = body.length > 200
  const owner = activity.repo_owner
  const repo = activity.repo_name
  const target = activity.target_type
  const isDiscussion = target === "issue" || target === "pull_request"
  const state =
    activity.preview?.state ??
    (activity.kind.endsWith("merge")
      ? "merged"
      : activity.kind.endsWith("close")
        ? "closed"
        : isDiscussion
          ? "open"
          : undefined)
  const StatusIcon = state === "merged" ? GitMerge : target === "pull_request" ? GitPullRequest : CircleDot
  const bodyId = `feed-body-${activity.id}`
  const copyLink = async () => {
    if (!owner || !repo) return
    const base = `/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}`
    const path =
      isDiscussion && activity.target_number != null
        ? `${base}/${target === "issue" ? "issues" : "pulls"}/${activity.target_number}`
        : target === "release"
          ? `${base}/releases`
          : base
    if (await copy(`${window.location.origin}${path}`)) showSuccessToast("Link copied to clipboard.")
    else showErrorToast("Unable to copy the link.")
  }

  return (
    <article className="overflow-hidden rounded-lg border border-border bg-card">
      <header className="flex items-start justify-between gap-3 px-4 py-3">
        <div className="flex min-w-0 items-start gap-2">
          <Link
            to="/profile/$username"
            params={{ username: activity.actor_username }}
            aria-label={`View ${activity.actor_username}'s profile`}
            appearance="avatar"
          >
            {activity.actor_username.slice(0, 1).toUpperCase()}
          </Link>
          <div className="min-w-0 [overflow-wrap:anywhere]">
            <p className="text-sm leading-5 text-foreground">
              <Link to="/profile/$username" params={{ username: activity.actor_username }} appearance="author">
                {activity.actor_username}
              </Link>{" "}
              {activityActions[activity.kind] ?? activity.kind}{" "}
              {owner && repo && (
                <Link to="/$owner/$repo" params={{ owner, repo }} appearance="strong">
                  {owner}/{repo}
                </Link>
              )}
            </p>
            {activity.created_at && (
              <time
                dateTime={activity.created_at}
                title={new Date(activity.created_at).toLocaleString()}
                className="block text-xs leading-4 text-muted-foreground"
              >
                {formatTime(activity.created_at)}
              </time>
            )}
          </div>
        </div>
        {owner && repo && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button type="button" aria-label="Activity options" variant="quiet" size="compact">
                <MoreHorizontal className="size-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem asChild>
                <TargetLink activity={activity}>View activity</TargetLink>
              </DropdownMenuItem>
              <DropdownMenuItem onSelect={copyLink}>Copy link</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      </header>
      {activity.title && (
        <div className="px-4 pb-4">
          <h3 className="mb-2 break-words text-base font-semibold [overflow-wrap:anywhere]">
            <TargetLink activity={activity} appearance="target">
              {activity.title}
              {activity.target_number != null && (
                <>
                  {" "}
                  <span className="font-normal text-muted-foreground">#{activity.target_number}</span>
                </>
              )}
            </TargetLink>
          </h3>
          {isDiscussion && state && (
            <div className="mb-3 flex items-center gap-2">
              <span
                className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${state === "merged" ? "bg-merged text-merged-foreground" : state === "closed" ? "bg-destructive/15 text-destructive" : "bg-success/15 text-success"}`}
              >
                <StatusIcon className="size-3" aria-hidden="true" />
                {state === "merged" ? "Merged" : state === "closed" ? "Closed" : "Open"}
              </span>
              <span className="text-xs text-muted-foreground">
                {target === "pull_request" ? "Pull request" : "Issue"}
              </span>
            </div>
          )}
          {body && (
            <div id={bodyId} className="rounded-lg bg-secondary p-4">
              {activity.kind === "comment" && <p className="mb-2 text-xs text-muted-foreground">Comment</p>}
              <Description text={expanded || !isLong ? body : `${body.slice(0, 200).trimEnd()}…`} />
              {expanded && activity.preview?.body_truncated && (
                <TargetLink activity={activity} appearance="preview">
                  {activity.kind === "comment" ? "View full comment" : "View full description"}
                </TargetLink>
              )}
            </div>
          )}
          {!body && activity.kind === "comment" && (
            <p className="rounded-lg bg-secondary p-4 text-sm text-muted-foreground">Comment preview unavailable.</p>
          )}
          {isLong && (
            <Button
              type="button"
              aria-expanded={expanded}
              aria-controls={bodyId}
              onClick={() => setExpanded((value) => !value)}
              variant="readMore"
              size="text"
            >
              {expanded ? "Show less" : "Read more"}
            </Button>
          )}
          {isDiscussion && (
            <footer className="mt-3 flex items-center gap-4 text-xs text-muted-foreground">
              <TargetLink activity={activity} appearance="comments">
                <MessageSquare className="size-3.5" aria-hidden="true" />
                {activity.preview?.comments_count
                  ? `${activity.preview.comments_count} ${activity.preview.comments_count === 1 ? "comment" : "comments"}`
                  : "Join the discussion"}
              </TargetLink>
            </footer>
          )}
        </div>
      )}
    </article>
  )
}

export default ActivityCard
