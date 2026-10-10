import { useQuery } from "@tanstack/react-query"
import { useState } from "react"

import { activityGetRepositoryActivityStatisticsOptions } from "@/client/@tanstack/react-query.gen"
import ActivityChart from "@/components/Repository/ActivityChart"
import ActivityContributors from "@/components/Repository/ActivityContributors"
import ActivityPulse from "@/components/Repository/ActivityPulse"
import ActivityRecentCommits from "@/components/Repository/ActivityRecentCommits"

interface RepositoryActivityProps {
  owner: string
  repo: string
}

const views = [
  { key: "pulse", label: "Pulse" },
  { key: "contributors", label: "Contributors" },
  { key: "code-frequency", label: "Code frequency" },
  { key: "recent-commits", label: "Recent commits" },
] as const

const RepositoryActivity = ({ owner, repo }: RepositoryActivityProps) => {
  const [view, setView] = useState<(typeof views)[number]["key"]>("pulse")
  const [days, setDays] = useState(7)
  const { data, isPending, isError, refetch } = useQuery({
    ...activityGetRepositoryActivityStatisticsOptions({ path: { owner, repo }, query: { days } }),
    staleTime: 60_000,
  })

  return (
    <div className="flex flex-col gap-6 md:flex-row" data-testid="repository-activity">
      <nav className="w-full shrink-0 md:w-48" aria-label="Repository activity">
        <div className="flex gap-1 overflow-x-auto md:flex-col md:overflow-visible">
          {views.map((item) => (
            <button
              key={item.key}
              type="button"
              aria-pressed={view === item.key}
              aria-controls="activity-content"
              onClick={() => setView(item.key)}
              className={`whitespace-nowrap rounded px-3 py-2 text-left text-sm transition-colors focus-visible:outline-2 focus-visible:outline-ring ${
                view === item.key
                  ? "bg-accent font-medium text-foreground"
                  : "text-muted-foreground hover:bg-accent/50 hover:text-foreground"
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
      </nav>
      <div id="activity-content" className="min-w-0 flex-1" aria-busy={isPending}>
        {isPending && (
          <p role="status" className="py-12 text-center text-sm text-muted-foreground">
            Loading activity…
          </p>
        )}
        {isError && (
          <div role="alert" className="space-y-3 rounded-lg border border-border p-6 text-center">
            <p className="text-sm text-muted-foreground">Could not load repository activity.</p>
            <button
              type="button"
              onClick={() => refetch()}
              className="rounded border border-border bg-secondary px-3 py-1.5 text-sm"
            >
              Try again
            </button>
          </div>
        )}
        {data && !isError && (
          <>
            {view === "pulse" && <ActivityPulse data={data} owner={owner} repo={repo} days={days} setDays={setDays} />}
            {view === "contributors" && (
              <ActivityContributors contributors={data.contributors} series={data.code_frequency} />
            )}
            {view === "code-frequency" && (
              <div className="space-y-4">
                <h2 className="text-lg font-medium text-foreground">Code frequency</h2>
                <div className="rounded-lg border border-border p-4">
                  {data.code_frequency.length ? (
                    <ActivityChart
                      series={data.code_frequency}
                      variant="frequency"
                      height={256}
                      label="Weekly additions and deletions"
                    />
                  ) : (
                    <p className="py-12 text-center text-sm text-muted-foreground">No code changes yet.</p>
                  )}
                </div>
              </div>
            )}
            {view === "recent-commits" && <ActivityRecentCommits series={data.recent_commits} />}
          </>
        )}
      </div>
    </div>
  )
}

export default RepositoryActivity
