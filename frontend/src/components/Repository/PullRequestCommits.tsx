import { useQuery } from "@tanstack/react-query"
import { useState } from "react"
import { repositoriesGetPullRequestCommitsOptions } from "@/client/@tanstack/react-query.gen"
import { Button, Link as RouterLink } from "@/components/design-system"
import RepositoryLoading, { RepositoryError } from "./RepositoryLoading"

export const PullRequestCommits = ({ owner, repo, number }: { owner: string; repo: string; number: number }) => {
  const [offset, setOffset] = useState(0)
  const { data, isPending, isError, refetch } = useQuery(
    repositoriesGetPullRequestCommitsOptions({ path: { owner, repo, number }, query: { offset, limit: 50 } }),
  )
  if (isPending) return <RepositoryLoading label="Loading pull request commits" />
  if (isError) return <RepositoryError message="Unable to load commits." retry={() => refetch()} />
  return (
    <div className="space-y-4" data-testid="pr-commits">
      <div className="overflow-hidden rounded-lg border border-border">
        {!data?.data.length && (
          <p className="p-6 text-sm text-muted-foreground">No commits ahead of the base branch.</p>
        )}
        {data?.data.map((commit) => (
          <div
            key={commit.sha}
            className="flex flex-col justify-between gap-2 border-b border-border px-4 py-3 last:border-0 hover:bg-accent/30 sm:flex-row sm:items-center"
          >
            <div className="flex min-w-0 items-center gap-3">
              <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-accent text-xs font-medium text-accent-foreground">
                {commit.author.charAt(0).toUpperCase()}
              </span>
              <div className="min-w-0">
                <RouterLink
                  to="/$owner/$repo/commit/$hash"
                  params={{ owner, repo, hash: commit.sha }}
                  appearance="commitSubject"
                  title={commit.message}
                >
                  {commit.message.split("\n")[0]}
                </RouterLink>
                <p className="text-xs text-muted-foreground">
                  {commit.author} committed{" "}
                  <time dateTime={new Date(commit.timestamp * 1000).toISOString()}>
                    {new Date(commit.timestamp * 1000).toLocaleString()}
                  </time>
                </p>
              </div>
            </div>
            <div className="pl-9 sm:ml-4 sm:pl-0">
              <RouterLink
                to="/$owner/$repo/commit/$hash"
                params={{ owner, repo, hash: commit.sha }}
                appearance="commitPill"
              >
                {commit.sha.slice(0, 10)}
              </RouterLink>
            </div>
          </div>
        ))}
      </div>
      {data && data.count > 50 && (
        <div className="flex items-center justify-end gap-3 text-sm">
          <span>
            {offset + 1}–{Math.min(offset + 50, data.count)} of {data.count}
          </span>
          <Button
            variant="repository"
            size="compact"
            disabled={offset === 0}
            onClick={() => setOffset(Math.max(0, offset - 50))}
          >
            Previous
          </Button>
          <Button
            variant="repository"
            size="compact"
            disabled={offset + 50 >= data.count}
            onClick={() => setOffset(offset + 50)}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  )
}
