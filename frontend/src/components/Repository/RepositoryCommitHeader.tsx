import type { CommitInfo } from "@/client"
import { Button, Link, Skeleton } from "@/components/design-system"
import { formatRelativeTime } from "@/utils"

const RepositoryCommitHeader = ({
  owner,
  repo,
  commit,
  loading,
  error,
  onRetry,
}: {
  owner: string
  repo: string
  commit?: CommitInfo | null
  loading?: boolean
  error?: boolean
  onRetry?: () => void
}) => {
  if (!commit && !loading && !error) return null
  return (
    <div
      className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1 border-b border-border bg-secondary px-4 py-2.5"
      data-testid="last-commit-header"
    >
      {commit ? (
        <>
          <span
            aria-hidden="true"
            className="flex size-6 shrink-0 items-center justify-center rounded-full bg-accent text-xs font-medium text-accent-foreground"
          >
            {commit.author.charAt(0).toUpperCase()}
          </span>
          <span className="text-sm font-medium text-foreground">{commit.author}</span>
          <Link
            to="/$owner/$repo/commit/$hash"
            params={{ owner, repo, hash: commit.sha }}
            appearance="code"
            data-testid="last-commit-sha"
          >
            {commit.sha.slice(0, 10)}
          </Link>
          <Link
            to="/$owner/$repo/commit/$hash"
            params={{ owner, repo, hash: commit.sha }}
            appearance="commitMessage"
            title={commit.message}
          >
            {commit.message.split("\n")[0]}
          </Link>
          <time
            className="ml-auto whitespace-nowrap text-sm text-muted-foreground"
            dateTime={new Date(commit.timestamp * 1000).toISOString()}
          >
            {formatRelativeTime(commit.timestamp)}
          </time>
        </>
      ) : loading ? (
        <div role="status" aria-label="Loading latest commit" className="flex w-full items-center gap-3">
          <Skeleton appearance="fileMeta" />
          <Skeleton appearance="fileTitle" />
        </div>
      ) : (
        <div role="alert" className="flex flex-wrap items-center gap-2 text-sm text-destructive">
          Unable to load the latest commit.
          {onRetry && (
            <Button variant="text" size="text" onClick={onRetry}>
              Try again
            </Button>
          )}
        </div>
      )}
    </div>
  )
}
export default RepositoryCommitHeader
