import { useQuery } from "@tanstack/react-query"
import { Link as RouterLink } from "@tanstack/react-router"
import { GitPullRequest } from "lucide-react"
import { repositoriesListPullRequestsOptions } from "@/client/@tanstack/react-query.gen"
import RepositoryLoading, { RepositoryError } from "@/components/Repository/RepositoryLoading"
import TrackerFilters, { useTrackerFilters } from "@/components/Repository/TrackerFilters"

interface PullRequestsListProps {
  owner: string
  repo: string
}

const PullRequestsList = ({ owner, repo }: PullRequestsListProps) => {
  const {
    data: pullsData,
    isPending,
    isError,
    refetch,
  } = useQuery({
    ...repositoriesListPullRequestsOptions({ path: { owner, repo } }),
  })

  const filters = useTrackerFilters(pullsData?.data ?? [])
  const pulls = filters.filtered
  const openCount = pullsData?.open_count ?? 0
  const closedCount = pullsData?.closed_count ?? 0

  if (isPending) return <RepositoryLoading label="Loading pull requests" />
  if (isError) return <RepositoryError message="Unable to load pull requests." retry={() => refetch()} />

  return (
    <div className="space-y-4">
      <TrackerFilters filters={filters} label="pull requests" openCount={openCount} closedCount={closedCount}>
        <RouterLink
          to="/$owner/$repo/pulls/new"
          params={{ owner, repo }}
          className="rounded bg-success px-4 py-2 text-sm font-medium text-success-foreground hover:opacity-90"
          data-testid="new-pr-btn"
        >
          New pull request
        </RouterLink>
      </TrackerFilters>
      <div className="overflow-hidden rounded-lg border">
        {pulls.length > 0 ? (
          <div>
            {pulls.map((pr) => (
              <div
                key={pr.id}
                className="flex items-center gap-3 px-4 py-3 border-b border-border last:border-b-0 hover:bg-accent/50 transition-colors"
                data-testid={`pr-${pr.number}`}
              >
                <GitPullRequest
                  className={`w-4 h-4 flex-shrink-0 ${pr.state === "open" ? "text-success" : pr.state === "merged" ? "text-purple-500" : "text-muted-foreground"}`}
                />
                <div className="flex-1 min-w-0">
                  <RouterLink
                    to="/$owner/$repo/pulls/$number"
                    params={{ owner, repo, number: String(pr.number) }}
                    className="text-sm font-medium text-foreground hover:text-primary"
                  >
                    {pr.title}
                  </RouterLink>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    #{pr.number} {pr.head_branch} &rarr; {pr.base_branch}
                    {pr.created_at && ` opened ${new Date(pr.created_at).toLocaleDateString()}`}
                  </p>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div
            className="flex flex-col items-center justify-center py-12 text-muted-foreground"
            data-testid="pulls-empty-state"
          >
            <GitPullRequest className="w-12 h-12 mb-3 opacity-50" />
            <p className="text-sm font-medium">
              {filters.search || filters.state !== "all" || filters.author
                ? "No matching pull requests"
                : "No pull requests yet"}
            </p>
            <p className="text-xs mt-1">Pull requests help you collaborate on code with others.</p>
          </div>
        )}
      </div>
    </div>
  )
}

export default PullRequestsList
