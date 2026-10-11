import { useQuery } from "@tanstack/react-query"
import { Link as RouterLink } from "@tanstack/react-router"
import { CircleDot, MessageSquare } from "lucide-react"
import { repositoriesListIssuesOptions } from "@/client/@tanstack/react-query.gen"
import RepositoryLoading, { RepositoryError } from "@/components/Repository/RepositoryLoading"
import TrackerFilters, { useTrackerFilters } from "@/components/Repository/TrackerFilters"

interface IssuesListProps {
  owner: string
  repo: string
}

const IssuesList = ({ owner, repo }: IssuesListProps) => {
  const {
    data: issuesData,
    isPending,
    isError,
    refetch,
  } = useQuery({
    ...repositoriesListIssuesOptions({ path: { owner, repo } }),
  })

  const filters = useTrackerFilters(issuesData?.data ?? [])
  const issues = filters.filtered
  const openCount = issuesData?.open_count ?? 0
  const closedCount = issuesData?.closed_count ?? 0

  if (isPending) return <RepositoryLoading label="Loading issues" />
  if (isError) return <RepositoryError message="Unable to load issues." retry={() => refetch()} />

  return (
    <div className="space-y-4">
      <TrackerFilters filters={filters} label="issues" openCount={openCount} closedCount={closedCount}>
        <RouterLink
          to="/$owner/$repo/issues/new"
          params={{ owner, repo }}
          className="rounded bg-success px-4 py-2 text-sm font-medium text-success-foreground hover:opacity-90"
          data-testid="new-issue-btn"
        >
          New issue
        </RouterLink>
      </TrackerFilters>
      <div className="overflow-hidden rounded-lg border">
        {issues.length > 0 ? (
          <div>
            {issues.map((issue) => (
              <div
                key={issue.id}
                className="flex items-center gap-3 px-4 py-3 border-b border-border last:border-b-0 hover:bg-accent/50 transition-colors"
                data-testid={`issue-${issue.number}`}
              >
                <CircleDot
                  className={`w-4 h-4 flex-shrink-0 ${issue.state === "open" ? "text-success" : "text-muted-foreground"}`}
                />
                <div className="flex-1 min-w-0">
                  <RouterLink
                    to="/$owner/$repo/issues/$number"
                    params={{ owner, repo, number: String(issue.number) }}
                    className="text-sm font-medium text-foreground hover:text-primary"
                  >
                    {issue.title}
                  </RouterLink>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    #{issue.number}
                    {issue.created_at && ` opened ${new Date(issue.created_at).toLocaleDateString()}`}
                  </p>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div
            className="flex flex-col items-center justify-center py-12 text-muted-foreground"
            data-testid="issues-empty-state"
          >
            <MessageSquare className="w-12 h-12 mb-3 opacity-50" />
            <p className="text-sm font-medium">
              {filters.search || filters.state !== "all" || filters.author ? "No matching issues" : "No issues yet"}
            </p>
            <p className="text-xs mt-1">Issues are used to track bugs, enhancements, and tasks.</p>
          </div>
        )}
      </div>
    </div>
  )
}

export default IssuesList
