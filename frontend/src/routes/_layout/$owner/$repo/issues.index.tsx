import { useQuery } from "@tanstack/react-query"
import { createFileRoute, Link as RouterLink } from "@tanstack/react-router"
import { CircleDot, MessageSquare, Search } from "lucide-react"

import { RepositoriesService } from "@/client"

export const Route = createFileRoute("/_layout/$owner/$repo/issues/")({
  component: IssuesIndex,
  head: ({ params }) => ({
    meta: [
      {
        title: `Issues - ${params.owner}/${params.repo} - GitEdge`,
      },
    ],
  }),
})

function IssuesContent({ owner, repo }: { owner: string; repo: string }) {
  const repoPath = `${owner}/${repo}.git`

  const { data: issuesData } = useQuery({
    queryKey: ["issues", repoPath],
    queryFn: async () =>
      (await RepositoriesService.listIssues({ path: { path: repoPath } })).data,
  })

  const issues = issuesData?.data ?? []
  const openCount = issuesData?.open_count ?? 0
  const closedCount = issuesData?.closed_count ?? 0

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex items-center gap-2">
        <button
          type="button"
          className="px-3 py-1.5 text-sm rounded border border-border bg-secondary text-foreground hover:bg-accent transition-colors"
        >
          Labels
        </button>
        <button
          type="button"
          className="px-3 py-1.5 text-sm rounded border border-border bg-secondary text-foreground hover:bg-accent transition-colors"
        >
          Milestones
        </button>
        <div className="flex-1 flex items-center gap-2">
          <input
            type="text"
            placeholder="Search issues..."
            className="flex-1 px-3 py-1.5 text-sm bg-secondary border border-border rounded text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
          />
          <button
            type="button"
            className="p-1.5 rounded border border-border bg-secondary hover:bg-accent transition-colors"
          >
            <Search className="w-4 h-4 text-muted-foreground" />
          </button>
        </div>
        <RouterLink
          to="/$owner/$repo/issues/new"
          params={{ owner, repo }}
          className="px-4 py-1.5 text-sm rounded bg-success text-success-foreground font-medium hover:opacity-90 transition-opacity"
          data-testid="new-issue-btn"
        >
          New issue
        </RouterLink>
      </div>

      {/* Issue list */}
      <div className="border border-border rounded-lg overflow-hidden">
        {/* Stats bar */}
        <div className="flex items-center justify-between px-4 py-2.5 bg-secondary border-b border-border">
          <div className="flex items-center gap-4 text-sm">
            <span className="flex items-center gap-1.5 text-foreground font-medium">
              <CircleDot className="w-4 h-4" />
              {openCount} Open
            </span>
            <span className="flex items-center gap-1.5 text-muted-foreground">
              <CircleDot className="w-4 h-4" />
              {closedCount} Closed
            </span>
          </div>
          <div className="flex items-center gap-3 text-sm text-muted-foreground">
            <button
              type="button"
              className="hover:text-foreground transition-colors"
            >
              Label
            </button>
            <button
              type="button"
              className="hover:text-foreground transition-colors"
            >
              Author
            </button>
            <button
              type="button"
              className="hover:text-foreground transition-colors"
            >
              Assignee
            </button>
            <button
              type="button"
              className="hover:text-foreground transition-colors"
            >
              Sort
            </button>
          </div>
        </div>

        {/* Issues list or empty state */}
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
                  <span className="text-sm font-medium text-foreground hover:text-primary">
                    {issue.title}
                  </span>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    #{issue.number}
                    {issue.created_at &&
                      ` opened ${new Date(issue.created_at).toLocaleDateString()}`}
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
            <p className="text-sm font-medium">No issues yet</p>
            <p className="text-xs mt-1">
              Issues are used to track bugs, enhancements, and tasks.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}

function IssuesIndex() {
  const { owner, repo } = Route.useParams()

  return <IssuesContent owner={owner} repo={repo} />
}
