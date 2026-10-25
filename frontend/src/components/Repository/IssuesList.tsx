import { useQuery } from "@tanstack/react-query"
import { CircleDot, MessageSquare } from "lucide-react"
import { repositoriesListIssuesOptions } from "@/client/@tanstack/react-query.gen"
import { Link as RouterLink } from "@/components/design-system"
import RepositoryLoading, { RepositoryError } from "@/components/Repository/RepositoryLoading"
import TrackerFilters, { TrackerSearch, useTrackerFilters } from "@/components/Repository/TrackerFilters"

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
    ...repositoriesListIssuesOptions({ path: { owner, repo }, query: { state: "all" } }),
  })

  const filters = useTrackerFilters(issuesData?.data ?? [])
  const issues = filters.filtered
  const openCount = issuesData?.open_count ?? 0
  const closedCount = issuesData?.closed_count ?? 0

  if (isPending) return <RepositoryLoading label="Loading issues" />
  if (isError) return <RepositoryError message="Unable to load issues." retry={() => refetch()} />

  return (
    <div className="space-y-4">
      <TrackerSearch filters={filters} label="issues">
        <RouterLink
          to="/$owner/$repo/issues/new"
          params={{ owner, repo }}
          appearance="trackerAction"
          data-testid="new-issue-btn"
        >
          New issue
        </RouterLink>
      </TrackerSearch>
      <div className="overflow-hidden rounded-lg border border-border">
        <TrackerFilters
          filters={filters}
          kind="issues"
          openCount={openCount}
          closedCount={closedCount}
          totalCount={issuesData?.count ?? 0}
        />
        {issues.length > 0 ? (
          <div>
            {issues.map((issue) => (
              <div
                key={issue.id}
                className="flex items-start gap-3 px-4 py-3 border-b border-border last:border-b-0 hover:bg-accent/30 transition-colors"
                data-testid={`issue-${issue.number}`}
              >
                <CircleDot
                  className={`w-4 h-4 mt-0.5 flex-shrink-0 ${issue.state === "open" ? "text-success" : "text-muted-foreground"}`}
                />
                <div className="flex-1 min-w-0">
                  <RouterLink
                    to="/$owner/$repo/issues/$number"
                    params={{ owner, repo, number: String(issue.number) }}
                    appearance="title"
                  >
                    {issue.title}
                  </RouterLink>
                  <p className="text-xs text-muted-foreground mt-1">
                    #{issue.number}
                    {issue.created_at && ` opened ${new Date(issue.created_at).toLocaleDateString()}`} by{" "}
                    {issue.author_username}
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
            <p className="text-sm font-medium">{issuesData?.count ? "No matching issues" : "No issues yet"}</p>
            <p className="text-xs mt-1">Issues are used to track bugs, enhancements, and tasks.</p>
          </div>
        )}
      </div>
    </div>
  )
}

export default IssuesList
