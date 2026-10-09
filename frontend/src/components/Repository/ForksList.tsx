import { Link as RouterLink } from "@tanstack/react-router"
import { GitFork } from "lucide-react"

import type { ForkPublic } from "@/client"

interface ForksListProps {
  forks: ForkPublic[]
}

const ForksList = ({ forks }: ForksListProps) => {
  if (forks.length === 0) {
    return <div className="py-12 text-center text-sm text-muted-foreground">No forks yet.</div>
  }

  return (
    <div className="space-y-2" data-testid="forks-list">
      {forks.map((fork) => (
        <div key={fork.id} className="flex items-center gap-3 border border-border rounded-lg bg-card px-4 py-3">
          <GitFork className="w-4 h-4 text-muted-foreground" />
          <div className="min-w-0">
            {fork.owner ? (
              <RouterLink
                to="/$owner/$repo"
                params={{ owner: fork.owner, repo: fork.name }}
                className="text-sm font-medium text-primary hover:underline"
              >
                {fork.owner}/{fork.name}
              </RouterLink>
            ) : (
              <span className="text-sm font-medium text-foreground">{fork.name}</span>
            )}
            {fork.description && <p className="text-xs text-muted-foreground truncate">{fork.description}</p>}
          </div>
          <div className="ml-auto flex items-center gap-3 text-xs text-muted-foreground">
            <span className="flex items-center gap-1">★ {fork.stars_count}</span>
            <span className="flex items-center gap-1">
              <GitFork className="w-3 h-3" /> {fork.forks_count}
            </span>
          </div>
        </div>
      ))}
    </div>
  )
}

export default ForksList
