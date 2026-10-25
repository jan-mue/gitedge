import { useQuery } from "@tanstack/react-query"
import { GitPullRequest } from "lucide-react"
import { repositoriesListPullRequestsOptions } from "@/client/@tanstack/react-query.gen"
import { Link as RouterLink } from "@/components/design-system"
import RepositoryLoading, { RepositoryError } from "@/components/Repository/RepositoryLoading"
import TrackerFilters, { TrackerSearch, useTrackerFilters } from "@/components/Repository/TrackerFilters"

interface PullRequestsListProps {
  owner: string
  repo: string
}

export const PullRequestsList = ({ owner, repo }: PullRequestsListProps) => {
  const {
    data: pullsData,
    isPending,
    isError,
    refetch,
  } = useQuery({
    ...repositoriesListPullRequestsOptions({ path: { owner, repo }, query: { state: "all" } }),
  })

  const filters = useTrackerFilters(pullsData?.data ?? [])
  const pulls = filters.filtered
  const openCount = pullsData?.open_count ?? 0
  const closedCount = pullsData?.closed_count ?? 0

  if (isPending) return <RepositoryLoading label="Loading pull requests" />
  if (isError) return <RepositoryError message="Unable to load pull requests." retry={() => refetch()} />

  return (
    <div className="space-y-4">
      <TrackerSearch filters={filters} label="pull requests">
        <RouterLink
          to="/$owner/$repo/pulls/new"
          params={{ owner, repo }}
          appearance="trackerAction"
          data-testid="new-pr-btn"
        >
          New pull request
        </RouterLink>
      </TrackerSearch>
      <div className="overflow-hidden rounded-lg border border-border">
        <TrackerFilters
          filters={filters}
          kind="pulls"
          openCount={openCount}
          closedCount={closedCount}
          totalCount={pullsData?.count ?? 0}
          mergedCount={pullsData?.data.filter((pr) => pr.state === "merged").length ?? 0}
        />
        {pulls.length > 0 ? (
          <div>
            {pulls.map((pr) => (
              <div
                key={pr.id}
                className="flex items-start gap-3 px-4 py-3 border-b border-border last:border-b-0 hover:bg-accent/30 transition-colors"
                data-testid={`pr-${pr.number}`}
              >
                <GitPullRequest
                  className={`w-4 h-4 mt-0.5 flex-shrink-0 ${pr.state === "open" ? "text-success" : pr.state === "merged" ? "text-merged" : "text-muted-foreground"}`}
                />
                <div className="flex-1 min-w-0">
                  <RouterLink
                    to="/$owner/$repo/pulls/$number"
                    params={{ owner, repo, number: String(pr.number) }}
                    appearance="title"
                  >
                    {pr.title}
                  </RouterLink>
                  <p className="text-xs text-muted-foreground mt-1">
                    #{pr.number}
                    {pr.created_at && ` opened ${new Date(pr.created_at).toLocaleDateString()}`} by {pr.author_username}
                    <span className="ml-2">
                      {pr.head_branch} &rarr; {pr.base_branch}
                    </span>
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
              {pullsData?.count ? "No matching pull requests" : "No pull requests yet"}
            </p>
            <p className="text-xs mt-1">Pull requests help you collaborate on code with others.</p>
          </div>
        )}
      </div>
    </div>
  )
}
