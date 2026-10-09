import { useQuery } from "@tanstack/react-query"
import { Link as RouterLink } from "@tanstack/react-router"
import { GitBranch, Search } from "lucide-react"
import { useMemo, useState } from "react"

import { RepositoriesService } from "@/client"
import StarButton from "@/components/Repository/StarButton"

const RepoExplorer = () => {
  const [query, setQuery] = useState("")

  const { data } = useQuery({
    queryKey: ["repositories"],
    queryFn: async () => (await RepositoriesService.listRepositories()).data,
  })

  const repositories = useMemo(() => {
    const items = data?.data ?? []
    const term = query.trim().toLowerCase()
    if (!term) return items
    return items.filter(
      (repo) => repo.name.toLowerCase().includes(term) || (repo.description ?? "").toLowerCase().includes(term),
    )
  }, [data, query])

  return (
    <div className="container mx-auto max-w-7xl space-y-6 px-4 py-6" data-testid="explore-repositories">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Explore</h1>
          <p className="text-muted-foreground">Discover repositories across GitEdge</p>
        </div>
        <div className="relative w-72 max-w-full">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search repositories..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            data-testid="explore-search"
            className="w-full pl-9 pr-3 py-2 text-sm bg-secondary border border-border rounded text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </div>
      </div>

      {repositories.length > 0 ? (
        <div className="space-y-3">
          {repositories.map((repo) => (
            <div
              key={`${repo.owner}/${repo.name}`}
              className="flex items-start gap-4 border border-border rounded-lg bg-card px-4 py-3"
              data-testid={`explore-repo-${repo.name}`}
            >
              <GitBranch className="w-4 h-4 text-muted-foreground mt-1 flex-shrink-0" />
              <div className="min-w-0 flex-1">
                <RouterLink
                  to="/$owner/$repo"
                  params={{ owner: repo.owner, repo: repo.name }}
                  className="text-sm font-medium text-primary hover:underline"
                >
                  {repo.owner}/{repo.name}
                </RouterLink>
                {repo.description && <p className="text-xs text-muted-foreground mt-1">{repo.description}</p>}
              </div>
              <StarButton owner={repo.owner} repo={repo.name} />
            </div>
          ))}
        </div>
      ) : (
        <div className="py-12 text-center text-sm text-muted-foreground">No repositories found.</div>
      )}
    </div>
  )
}

export default RepoExplorer
