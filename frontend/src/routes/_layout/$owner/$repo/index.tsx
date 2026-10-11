import { useQuery } from "@tanstack/react-query"
import { createFileRoute, Navigate } from "@tanstack/react-router"

import { repositoriesGetRepositoryInfoOptions } from "@/client/@tanstack/react-query.gen"
import RepositoryLoading from "@/components/Repository/RepositoryLoading"

export const Route = createFileRoute("/_layout/$owner/$repo/")({
  component: RepositoryIndexRedirect,
})

function RepositoryIndexRedirect() {
  const { owner, repo } = Route.useParams()

  const { data, isError } = useQuery({
    ...repositoriesGetRepositoryInfoOptions({ path: { owner, repo } }),
  })

  if (isError) {
    return (
      <div
        className="flex items-center justify-center py-16 text-sm text-muted-foreground"
        data-testid="repository-not-found"
      >
        Repository not found.
      </div>
    )
  }

  if (!data) {
    return <RepositoryLoading label="Opening repository" />
  }

  return (
    <Navigate to="/$owner/$repo/src/branch/$branch" params={{ owner, repo, branch: data.default_branch }} replace />
  )
}
