import { useQuery } from "@tanstack/react-query"
import { createFileRoute, Navigate } from "@tanstack/react-router"
import { repositoriesGetRepositoryInfoOptions } from "@/client/@tanstack/react-query.gen"
import RepositoryLoading from "@/components/Repository/RepositoryLoading"
import { EmptyState } from "@/design-system"

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
      <div data-testid="repository-not-found">
        <EmptyState title="Repository not found." />
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
