import { useMemo, useState } from "react"

import type { ActivitySeriesPoint, ContributorActivity } from "@/client"
import ActivityChart, { type ActivityMetric } from "@/components/Repository/ActivityChart"

interface ActivityContributorsProps {
  contributors: ContributorActivity[]
  series: ActivitySeriesPoint[]
}

const ActivityContributors = ({ contributors, series }: ActivityContributorsProps) => {
  const [metric, setMetric] = useState<ActivityMetric>("commits")
  const sorted = useMemo(
    () =>
      [...contributors].sort(
        (first, second) => second[metric] - first[metric] || first.name.localeCompare(second.name),
      ),
    [contributors, metric],
  )
  const dateLabel = (value: string) =>
    new Date(`${value}T00:00:00Z`).toLocaleDateString("en-US", {
      month: "long",
      day: "numeric",
      year: "numeric",
      timeZone: "UTC",
    })

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg font-medium text-foreground">
          {series.length
            ? `${dateLabel(series[0].date)} - ${dateLabel(series[series.length - 1].date)}`
            : "Contributors"}
        </h2>
        <select
          aria-label="Contribution metric"
          value={metric}
          onChange={(event) => setMetric(event.target.value as ActivityMetric)}
          className="rounded border border-border bg-secondary px-3 py-1.5 text-sm text-foreground focus-visible:outline-2 focus-visible:outline-ring"
        >
          <option value="commits">Commits</option>
          <option value="additions">Additions</option>
          <option value="deletions">Deletions</option>
        </select>
      </div>
      <div className="rounded-lg border border-border p-4">
        {series.length ? (
          <>
            <p className="mb-2 text-center text-xs text-muted-foreground">
              drag: zoom, shift+drag: pan, double click: reset zoom
            </p>
            <p className="sr-only">Focus the chart and press plus to zoom in, minus or Escape to reset.</p>
            <ActivityChart
              key={metric}
              series={series}
              metric={metric}
              variant="area"
              interactive
              label={`Overall ${metric}`}
            />
          </>
        ) : (
          <p className="py-12 text-center text-sm text-muted-foreground">No contributions yet.</p>
        )}
      </div>
      {sorted.map((contributor, index) => (
        <div
          key={`${contributor.name}-${index}`}
          className="rounded-lg border border-border p-4"
          data-testid="activity-contributor"
        >
          <div className="mb-3 flex items-center justify-between">
            <div className="flex min-w-0 items-center gap-3">
              <div
                className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-accent text-sm font-medium text-accent-foreground"
                aria-hidden="true"
              >
                {contributor.name[0]?.toUpperCase() || "?"}
              </div>
              <div className="min-w-0">
                <span className="break-words text-sm font-medium text-primary">{contributor.name}</span>
                <div className="text-xs text-muted-foreground">
                  {contributor.commits.toLocaleString()} Commits{" "}
                  <span className="text-success">{contributor.additions.toLocaleString()}++</span>{" "}
                  <span className="text-destructive">{contributor.deletions.toLocaleString()}--</span>
                </div>
              </div>
            </div>
            <span className="ml-2 text-lg font-bold text-muted-foreground">#{index + 1}</span>
          </div>
          <ActivityChart
            series={contributor.series}
            metric={metric}
            height={80}
            label={`${contributor.name}: weekly ${metric}`}
          />
        </div>
      ))}
    </div>
  )
}

export default ActivityContributors
