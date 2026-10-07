import { useQuery } from "@tanstack/react-query"
import { Link as RouterLink } from "@tanstack/react-router"
import { Filter, GitMerge, MessageSquare, MoreHorizontal, Smile, TrendingUp, X } from "lucide-react"
import { useMemo, useState } from "react"

import type { ActivityPublic, Repository } from "@/client"
import { ActivityService, RepositoriesService } from "@/client"
import StarButton from "@/components/Repository/StarButton"
import useAuth from "@/hooks/useAuth"

const kindAction: Record<string, string> = {
  star: "starred",
  watch: "started watching",
  fork: "forked",
  issue_open: "opened issue",
  issue_close: "closed issue",
  issue_reopen: "reopened issue",
  comment: "commented on",
  pull_request_open: "opened pull request",
  pull_request_merge: "merged pull request",
  pull_request_close: "closed pull request",
  pull_request_reopen: "reopened pull request",
  release: "published release",
}

const ActivityCard = ({ activity }: { activity: ActivityPublic }) => {
  const owner = activity.repo_owner
  const repoName = activity.repo_name
  const isMerge = activity.kind === "pull_request_merge"

  return (
    <article className="overflow-hidden rounded-lg border border-border bg-card">
      <div className="px-4 py-3">
        <div className="flex items-start justify-between gap-3">
          <div className="flex min-w-0 items-center gap-2">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent text-sm font-medium text-accent-foreground">
              {(activity.actor_username ?? "?").slice(0, 1).toUpperCase()}
            </div>
            <div className="min-w-0">
              <p className="text-sm text-foreground">
                <span className="font-semibold">{activity.actor_username ?? "Someone"}</span>{" "}
                <span className="text-muted-foreground">{kindAction[activity.kind] ?? activity.kind}</span>{" "}
                {owner && repoName && (
                  <RouterLink
                    to="/$owner/$repo"
                    params={{ owner, repo: repoName }}
                    className="font-semibold text-primary hover:underline"
                  >
                    {owner}/{repoName}
                  </RouterLink>
                )}
              </p>
              {activity.created_at && (
                <p className="text-xs text-muted-foreground">{new Date(activity.created_at).toLocaleString()}</p>
              )}
            </div>
          </div>
          <button type="button" className="shrink-0 rounded p-1 transition-colors hover:bg-accent">
            <MoreHorizontal className="h-4 w-4 text-muted-foreground" />
          </button>
        </div>
      </div>

      {activity.title && (
        <div className="px-4 pb-4">
          <h3 className="mb-2 text-base font-semibold text-foreground">
            {activity.title}
            {activity.target_number != null && (
              <span className="font-normal text-muted-foreground"> #{activity.target_number}</span>
            )}
          </h3>
          {isMerge && (
            <div className="mb-3 flex items-center gap-2">
              <span className="flex items-center gap-1 rounded-full bg-[hsl(280_60%_35%)] px-2 py-0.5 text-xs font-medium text-white">
                <GitMerge className="h-3 w-3" /> Merged
              </span>
            </div>
          )}
          <div className="flex items-center gap-4">
            <button type="button" className="text-muted-foreground transition-colors hover:text-foreground">
              <Smile className="h-4 w-4" />
            </button>
            {activity.kind === "comment" && (
              <span className="flex items-center gap-1 text-xs text-muted-foreground">
                <MessageSquare className="h-3.5 w-3.5" /> comment
              </span>
            )}
          </div>
        </div>
      )}
    </article>
  )
}

const Feed = () => {
  const { user } = useAuth()
  const [showFilter, setShowFilter] = useState(false)

  const { data: feed } = useQuery({
    queryKey: ["feed"],
    queryFn: async () => (await ActivityService.getFeed()).data,
  })

  const { data: repositories } = useQuery({
    queryKey: ["repositories"],
    queryFn: async () => (await RepositoriesService.listRepositories()).data,
  })

  const activities = feed?.data ?? []
  const repos = repositories?.data ?? []

  const recentRepos = useMemo(() => repos.slice(0, 5), [repos])
  const recentPulls = useMemo(
    () => activities.filter((activity) => activity.target_type === "pull_request").slice(0, 5),
    [activities],
  )
  const trending = useMemo(
    () => [...repos].sort((a, b) => (b.stars_count ?? 0) - (a.stars_count ?? 0)).slice(0, 4),
    [repos],
  )

  return (
    <div className="container mx-auto max-w-7xl px-4 py-6" data-testid="dashboard-feed">
      <div className="grid grid-cols-1 items-start gap-6 md:grid-cols-[18rem_minmax(0,1fr)]">
        <aside className="hidden space-y-5 md:block">
          <section className="overflow-hidden rounded-lg border border-border bg-card">
            <div className="border-b border-border bg-secondary px-4 py-2.5">
              <h3 className="text-sm font-semibold text-foreground">Recently opened repositories</h3>
            </div>
            <div className="space-y-1 p-2">
              {recentRepos.map((repo: Repository) => (
                <RouterLink
                  key={`${repo.owner}/${repo.name}`}
                  to="/$owner/$repo"
                  params={{ owner: repo.owner, repo: repo.name }}
                  className="block rounded px-2 py-2 transition-colors hover:bg-accent/50"
                >
                  <p className="truncate text-sm font-medium text-foreground">
                    {repo.owner}/{repo.name}
                  </p>
                  <p className="truncate text-xs text-muted-foreground">{repo.description || "No description"}</p>
                </RouterLink>
              ))}
              {recentRepos.length === 0 && (
                <p className="px-2 py-3 text-xs text-muted-foreground">No repositories yet.</p>
              )}
            </div>
          </section>

          <section className="overflow-hidden rounded-lg border border-border bg-card">
            <div className="border-b border-border bg-secondary px-4 py-2.5">
              <h3 className="text-sm font-semibold text-foreground">Recent pull requests</h3>
            </div>
            <div className="space-y-1.5 p-2">
              {recentPulls.map((activity) => (
                <RouterLink
                  key={activity.id}
                  to="/$owner/$repo/pulls/$number"
                  params={{
                    owner: activity.repo_owner ?? "",
                    repo: activity.repo_name ?? "",
                    number: String(activity.target_number ?? 0),
                  }}
                  className="block rounded px-2 py-2 transition-colors hover:bg-accent/50"
                >
                  <p className="text-xs text-muted-foreground">{kindAction[activity.kind] ?? activity.kind}</p>
                  <p className="line-clamp-2 text-sm text-foreground">
                    {activity.title} <span className="text-primary">#{activity.target_number}</span>
                  </p>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    {activity.repo_owner}/{activity.repo_name}
                    {activity.created_at && ` · ${new Date(activity.created_at).toLocaleDateString()}`}
                  </p>
                </RouterLink>
              ))}
              {recentPulls.length === 0 && (
                <p className="px-2 py-3 text-xs text-muted-foreground">No pull requests yet.</p>
              )}
            </div>
          </section>
        </aside>

        <main className="min-w-0 space-y-4">
          <header className="flex items-center justify-between gap-3">
            <h1 className="text-xl font-semibold text-foreground">Feed</h1>
            <div className="relative">
              <button
                type="button"
                onClick={() => setShowFilter(!showFilter)}
                className="flex items-center gap-1.5 rounded border border-border bg-secondary px-3 py-1.5 text-sm text-foreground transition-colors hover:bg-accent"
              >
                <Filter className="h-3.5 w-3.5" /> Filter
              </button>
              {showFilter && (
                <div className="absolute right-0 top-full z-50 mt-1 w-72 space-y-3 rounded-lg border border-border bg-popover p-4 shadow-lg">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-semibold text-foreground">Filter</span>
                    <button type="button" onClick={() => setShowFilter(false)}>
                      <X className="h-4 w-4 text-muted-foreground" />
                    </button>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {user ? `Showing activity for ${user.name}` : "Showing activity"}
                  </p>
                </div>
              )}
            </div>
          </header>

          <div className="space-y-4">
            {activities.map((activity) => (
              <ActivityCard key={activity.id} activity={activity} />
            ))}
            {activities.length === 0 && (
              <div className="rounded-lg border border-border bg-card py-12 text-center text-sm text-muted-foreground">
                No activity yet. Create a repository to get started.
              </div>
            )}
          </div>

          <div className="overflow-hidden rounded-lg border border-border bg-card">
            <div className="flex items-center gap-2 border-b border-border px-4 py-3">
              <TrendingUp className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm font-medium text-foreground">Trending repositories</span>
              <span className="text-muted-foreground">·</span>
              <RouterLink to="/explore" className="text-sm text-primary hover:underline">
                See more
              </RouterLink>
            </div>
            {trending.map((repo: Repository, i: number) => (
              <div
                key={`${repo.owner}/${repo.name}`}
                className={`flex items-start justify-between gap-3 px-4 py-3 ${i < trending.length - 1 ? "border-b border-border" : ""}`}
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <div className="flex h-5 w-5 shrink-0 items-center justify-center rounded bg-accent text-[10px] font-bold text-accent-foreground">
                      {repo.name.slice(0, 1).toUpperCase()}
                    </div>
                    <RouterLink
                      to="/$owner/$repo"
                      params={{ owner: repo.owner, repo: repo.name }}
                      className="text-sm font-semibold text-primary hover:underline"
                    >
                      {repo.owner}/{repo.name}
                    </RouterLink>
                  </div>
                  <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">
                    {repo.description || "No description"}
                  </p>
                  <div className="mt-1.5 flex items-center gap-3 text-xs text-muted-foreground">
                    <span>{repo.stars_count ?? 0} stars</span>
                  </div>
                </div>
                <StarButton owner={repo.owner} repo={repo.name} />
              </div>
            ))}
          </div>
        </main>
      </div>
    </div>
  )
}

export default Feed
