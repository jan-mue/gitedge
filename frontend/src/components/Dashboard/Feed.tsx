import { useInfiniteQuery, useQuery } from "@tanstack/react-query"
import { Filter, TrendingUp, X } from "lucide-react"
import { useMemo, useState } from "react"
import type { Repository } from "@/client"
import { activityGetFeedInfiniteOptions, repositoriesListRepositoriesOptions } from "@/client/@tanstack/react-query.gen"
import ActivityCard, { activityActions as kindAction } from "@/components/Dashboard/ActivityCard"
import FeedLoading, { FeedListLoading } from "@/components/Dashboard/FeedLoading"
import { Button, LoadingButton, Link as RouterLink } from "@/components/design-system"
import { RepositoryError } from "@/components/Repository/RepositoryLoading"
import StarButton from "@/components/Repository/StarButton"
import useAuth from "@/hooks/useAuth"

const Feed = () => {
  const { user } = useAuth()
  const [showFilter, setShowFilter] = useState(false)

  const {
    data: feed,
    isPending: feedPending,
    isError: feedError,
    refetch: refetchFeed,
    hasNextPage,
    fetchNextPage,
    isFetchingNextPage,
    isFetchNextPageError,
  } = useInfiniteQuery({
    ...activityGetFeedInfiniteOptions({ query: { limit: 20 } }),
    initialPageParam: 0,
    getNextPageParam: (lastPage, pages) => (lastPage.count === 20 ? pages.length * 20 : undefined),
  })

  const {
    data: repositories,
    isPending: reposPending,
    isError: reposError,
    refetch: refetchRepos,
  } = useQuery({
    ...repositoriesListRepositoriesOptions(),
    enabled: Boolean(feed) || feedError,
  })

  const activities = useMemo(() => feed?.pages.flatMap((page) => page.data) ?? [], [feed])
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
              {reposPending ? (
                <FeedListLoading label="Loading repositories" />
              ) : reposError ? (
                <RepositoryError message="Unable to load repositories." retry={() => refetchRepos()} />
              ) : (
                recentRepos.map((repo: Repository) => (
                  <RouterLink
                    key={`${repo.owner}/${repo.name}`}
                    to="/$owner/$repo"
                    params={{ owner: repo.owner, repo: repo.name }}
                    appearance="default"
                  >
                    <p className="truncate text-sm font-medium text-foreground">
                      {repo.owner}/{repo.name}
                    </p>
                    <p className="truncate text-xs text-muted-foreground">{repo.description || "No description"}</p>
                  </RouterLink>
                ))
              )}
              {!reposPending && !reposError && recentRepos.length === 0 && (
                <p className="px-2 py-3 text-xs text-muted-foreground">No repositories yet.</p>
              )}
            </div>
          </section>

          <section className="overflow-hidden rounded-lg border border-border bg-card">
            <div className="border-b border-border bg-secondary px-4 py-2.5">
              <h3 className="text-sm font-semibold text-foreground">Recent pull requests</h3>
            </div>
            <div className="space-y-1.5 p-2">
              {feedPending ? (
                <FeedListLoading label="Loading pull requests" />
              ) : (
                !feedError &&
                recentPulls.map((activity) => (
                  <RouterLink
                    key={activity.id}
                    to="/$owner/$repo/pulls/$number"
                    params={{
                      owner: activity.repo_owner ?? "",
                      repo: activity.repo_name ?? "",
                      number: String(activity.target_number ?? 0),
                    }}
                    appearance="default"
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
                ))
              )}
              {!feedPending && !feedError && recentPulls.length === 0 && (
                <p className="px-2 py-3 text-xs text-muted-foreground">No pull requests yet.</p>
              )}
            </div>
          </section>
        </aside>

        <main className="min-w-0 space-y-4">
          <header className="flex items-center justify-between gap-3">
            <h1 className="text-xl font-semibold text-foreground">Feed</h1>
            <div className="relative">
              <Button type="button" onClick={() => setShowFilter(!showFilter)} variant="repository" size="compact">
                <Filter className="h-3.5 w-3.5" /> Filter
              </Button>
              {showFilter && (
                <div className="absolute right-0 top-full z-50 mt-1 w-72 space-y-3 rounded-lg border border-border bg-popover p-4 shadow-lg">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-semibold text-foreground">Filter</span>
                    <Button variant="ghost" size="compact" type="button" onClick={() => setShowFilter(false)}>
                      <X className="h-4 w-4 text-muted-foreground" />
                    </Button>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {user ? `Showing activity for ${user.name}` : "Showing activity"}
                  </p>
                </div>
              )}
            </div>
          </header>

          <div className="space-y-4" aria-busy={feedPending}>
            {feedPending ? (
              <FeedLoading />
            ) : feedError && !feed ? (
              <RepositoryError message="Unable to load your feed." retry={() => refetchFeed()} />
            ) : (
              activities.map((activity) => (
                <div key={activity.id} className="feed-content-enter">
                  <ActivityCard activity={activity} />
                </div>
              ))
            )}
            {!feedPending && !feedError && activities.length === 0 && (
              <div className="rounded-lg border border-border bg-card py-12 text-center text-sm text-muted-foreground">
                No activity yet. Create a repository to get started.
              </div>
            )}
            {feed && feedError && (
              <RepositoryError
                message={isFetchNextPageError ? "Unable to load more activity." : "Unable to refresh your feed."}
                retry={() => (isFetchNextPageError ? fetchNextPage() : refetchFeed())}
              />
            )}
            {hasNextPage && (
              <LoadingButton fullWidth variant="outline" loading={isFetchingNextPage} onClick={() => fetchNextPage()}>
                Load more activity
              </LoadingButton>
            )}
          </div>

          <div className="overflow-hidden rounded-lg border border-border bg-card">
            <div className="flex items-center gap-2 border-b border-border px-4 py-3">
              <TrendingUp className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm font-medium text-foreground">Trending repositories</span>
              <span className="text-muted-foreground">·</span>
              <RouterLink to="/explore" appearance="default">
                See more
              </RouterLink>
            </div>
            {reposPending ? (
              <FeedListLoading label="Loading trending repositories" />
            ) : reposError ? (
              <RepositoryError message="Unable to load trending repositories." retry={() => refetchRepos()} />
            ) : (
              trending.map((repo: Repository, i: number) => (
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
                        appearance="default"
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
              ))
            )}
          </div>
        </main>
      </div>
    </div>
  )
}

export default Feed
