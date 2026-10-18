// Adapted from jan-mue/gitea-clone's PullRequestDetailPage checks panel.
import type { ReactNode } from "react"
import { useId, useState } from "react"
import { Badge } from "./badge"
import { Button } from "./button"
import { type CheckStatus, CheckStatusIcon } from "./check-status-icon"

export interface PullRequestCheck {
  id: string
  name: string
  status: CheckStatus
  duration?: string
  required?: boolean
  details?: ReactNode
}

export const PullRequestChecks = ({
  checks,
  loading = false,
  error,
  retry,
  revision,
}: {
  checks: PullRequestCheck[]
  loading?: boolean
  error?: string
  retry?: () => void
  revision?: string
}) => {
  const [expanded, setExpanded] = useState(true)
  const id = useId()
  const pending = checks.some((check) => ["queued", "running"].includes(check.status))
  const failed = checks.some((check) => ["failure", "cancelled"].includes(check.status))
  const passed = checks.some((check) => check.status === "success")
  const status: CheckStatus = failed ? "failure" : pending || loading ? "running" : passed ? "success" : "skipped"
  const summary = error
    ? "Unable to load checks"
    : loading
      ? "Loading checks…"
      : failed
        ? "Some checks failed"
        : pending
          ? "Checks are running"
          : passed
            ? "All checks were successful"
            : checks.length
              ? "All checks were skipped"
              : "No checks reported"
  return (
    <section aria-label="Pull request checks" className="overflow-hidden rounded-lg border border-border">
      <Button
        variant="actionStep"
        size="file-row"
        aria-expanded={expanded}
        aria-controls={id}
        onClick={() => setExpanded((value) => !value)}
      >
        <CheckStatusIcon status={status} />
        <span className="flex-1 text-left font-medium">{summary}</span>
        <span className="shrink-0 text-xs text-muted-foreground">
          {expanded ? "Hide all checks" : "Show all checks"}
        </span>
      </Button>
      {expanded && (
        <div id={id} className="divide-y divide-border">
          {error ? (
            <div role="alert" className="flex items-center justify-between gap-3 px-4 py-3 text-sm">
              <span>{error}</span>
              {retry && (
                <Button variant="text" size="text" onClick={retry}>
                  Retry
                </Button>
              )}
            </div>
          ) : (
            checks.map((check) => (
              <div key={check.id} className="flex items-center gap-3 px-4 py-3 text-sm">
                <CheckStatusIcon status={check.status} />
                <span className="min-w-0 flex-1 break-words">{check.name}</span>
                {check.duration && <span className="shrink-0 text-xs text-muted-foreground">{check.duration}</span>}
                {check.required && <Badge variant="outline">Required</Badge>}
                {check.details}
              </div>
            ))
          )}
          {!error && !loading && !checks.length && (
            <p className="px-4 py-3 text-sm text-muted-foreground">Workflows will report their results here.</p>
          )}
          {revision && (
            <p className="px-4 py-2 text-xs text-muted-foreground">
              Checks for commit <code>{revision.slice(0, 10)}</code>
            </p>
          )}
        </div>
      )}
    </section>
  )
}
