import { Link } from "@tanstack/react-router"
import { CircleDot, GitPullRequest } from "lucide-react"

import type { RepositoryActivityStatistics } from "@/client"
import ActivityChart from "@/components/Repository/ActivityChart"

const formatDate = (value: string) =>
  new Date(value).toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric", timeZone: "UTC" })

const formatTime = (value: string) => {
  const hours = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 3_600_000))
  if (hours < 1) return "less than an hour ago"
  if (hours < 24) return `${hours} ${hours === 1 ? "hour" : "hours"} ago`
  const days = Math.floor(hours / 24)
  return days === 1 ? "yesterday" : `${days} days ago`
}

interface ActivityPulseProps {
  data: RepositoryActivityStatistics
  owner: string
  repo: string
  days: number
  setDays: (days: number) => void
}

const ActivityPulse = ({ data, owner, repo, days, setDays }: ActivityPulseProps) => {
  const overview = data.overview
  const stats = [
    { label: "Merged pull requests", value: overview.merged_prs, Icon: GitPullRequest, color: "text-primary" },
    { label: "Proposed pull requests", value: overview.proposed_prs, Icon: GitPullRequest, color: "text-success" },
    { label: "Closed issues", value: overview.closed_issues, Icon: CircleDot, color: "text-destructive" },
    { label: "New issues", value: overview.new_issues, Icon: CircleDot, color: "text-success" },
  ]
  const bars = [
    {
      label: "active pull requests",
      total: overview.active_prs,
      first: overview.merged_prs,
      second: overview.proposed_prs,
      color: "bg-primary",
    },
    {
      label: "active issues",
      total: overview.active_issues,
      first: overview.closed_issues,
      second: overview.new_issues,
      color: "bg-destructive",
    },
  ]

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg font-medium text-foreground sm:text-xl">
          {formatDate(data.start)} - {formatDate(data.end)}
        </h2>
        <select
          aria-label="Activity period"
          value={days}
          onChange={(event) => setDays(Number(event.target.value))}
          className="rounded border border-border bg-secondary px-3 py-1.5 text-sm text-foreground focus-visible:outline-2 focus-visible:outline-ring"
        >
          <option value={1}>1 day</option>
          <option value={3}>3 days</option>
          <option value={7}>1 week</option>
          <option value={30}>1 month</option>
        </select>
      </div>
      <div className="overflow-hidden rounded-lg border border-border">
        <div className="border-b border-border bg-secondary px-4 py-3 text-sm font-medium text-foreground">
          Overview
        </div>
        <div className="space-y-4 p-4">
          <div className="flex flex-col gap-4 sm:flex-row">
            {bars.map((bar) => (
              <div key={bar.label} className="flex-1">
                <div className="mb-2 flex h-3 overflow-hidden rounded bg-accent" aria-hidden="true">
                  <div
                    className={bar.color}
                    style={{ width: `${bar.first + bar.second ? (100 * bar.first) / (bar.first + bar.second) : 0}%` }}
                  />
                  <div
                    className="bg-success"
                    style={{ width: `${bar.first + bar.second ? (100 * bar.second) / (bar.first + bar.second) : 0}%` }}
                  />
                </div>
                <span className="text-sm text-foreground">
                  <strong>{bar.total}</strong> {bar.label}
                </span>
              </div>
            ))}
          </div>
          <div className="grid grid-cols-2 gap-4 text-center sm:grid-cols-4">
            {stats.map(({ label, value, Icon, color }) => (
              <div key={label} className="rounded border border-border p-3">
                <div className="flex items-center justify-center gap-1 text-lg font-bold text-foreground">
                  <Icon aria-hidden="true" className={`h-4 w-4 ${color}`} />
                  {value}
                </div>
                <div className="text-xs text-muted-foreground">{label}</div>
              </div>
            ))}
          </div>
          <div className="flex flex-col gap-4 overflow-hidden rounded-lg border border-border sm:flex-row">
            <div className="flex-1 p-4 text-sm text-foreground">
              Excluding merges, <strong>{overview.authors} authors</strong> have pushed{" "}
              <strong>{overview.commits} commits</strong> to {data.default_branch} and{" "}
              <strong>{overview.branch_commits} commits</strong> to all branches. On {data.default_branch},{" "}
              <strong>{overview.files_changed} files</strong> have changed and there have been{" "}
              <span className="font-medium text-success">{overview.additions.toLocaleString()} additions</span> and{" "}
              <span className="font-medium text-destructive">{overview.deletions.toLocaleString()} deletions</span>.
            </div>
            <div className="w-full shrink-0 p-2 sm:w-64">
              <ActivityChart
                series={data.daily_commits}
                height={112}
                daily
                label="Daily commits on the default branch"
              />
            </div>
          </div>
        </div>
      </div>
      <div>
        <div className="mb-3 flex items-center gap-2 border-b border-border pb-2 text-sm text-muted-foreground">
          <GitPullRequest aria-hidden="true" className="h-4 w-4" /> {overview.merged_prs} pull requests merged by{" "}
          {overview.merge_authors} users
        </div>
        <div className="space-y-1.5">
          {data.merged_prs.map((pr) => (
            <div key={pr.id} className="flex flex-wrap items-center gap-2 text-sm">
              <span className="rounded bg-primary px-2 py-0.5 text-xs font-medium text-primary-foreground">Merged</span>
              <span className="text-muted-foreground">#{pr.target_number}</span>
              {pr.target_number !== null && pr.target_number !== undefined && (
                <Link
                  to="/$owner/$repo/pulls/$number"
                  params={{ owner, repo, number: String(pr.target_number) }}
                  className="min-w-0 truncate text-primary hover:underline"
                >
                  {pr.title || `Pull request #${pr.target_number}`}
                </Link>
              )}
              <span className="text-xs text-muted-foreground" title={new Date(pr.created_at).toLocaleString()}>
                {formatTime(pr.created_at)}
              </span>
            </div>
          ))}
          {!data.merged_prs.length && (
            <p className="text-sm text-muted-foreground">No pull requests were merged during this period.</p>
          )}
        </div>
      </div>
    </div>
  )
}

export default ActivityPulse
