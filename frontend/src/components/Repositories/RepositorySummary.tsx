import type { Repository } from "@/client"
import { Link } from "@/components/design-system"

export const RepositorySummary = ({ repo }: { repo: Repository }) => {
  return (
    <div className="min-w-0 flex-1">
      <Link to="/$owner/$repo" params={{ owner: repo.owner, repo: repo.name }} appearance="repository">
        {repo.owner}/{repo.name}
      </Link>
      {repo.description && <p className="text-xs text-muted-foreground mt-1">{repo.description}</p>}
    </div>
  )
}
