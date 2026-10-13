import type { CommitInfo } from "@/client"
import { Button, Link, Skeleton } from "@/components/design-system"

const relativeDate = (timestamp: number) => {
  const age = (Date.now() / 1000 - timestamp) / 60
  if (age < 1) return "just now"
  if (age < 60) return `${Math.floor(age)} minutes ago`
  if (age < 1440) return `${Math.floor(age / 60)} hours ago`
  if (age < 43200) return `${Math.floor(age / 1440)} days ago`
  if (age < 525600) return `${Math.floor(age / 43200)} months ago`
  return `${Math.floor(age / 525600)} years ago`
}

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
          <span
            className="order-last w-full truncate text-sm text-foreground md:order-none md:w-auto md:min-w-0 md:flex-1"
            title={commit.message}
          >
            {commit.message.split("\n")[0]}
          </span>
          <time
            className="ml-auto whitespace-nowrap text-sm text-muted-foreground"
            dateTime={new Date(commit.timestamp * 1000).toISOString()}
          >
            {relativeDate(commit.timestamp)}
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
