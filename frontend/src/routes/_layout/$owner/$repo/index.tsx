import { useQuery } from "@tanstack/react-query"
import { createFileRoute, Navigate } from "@tanstack/react-router"

import { RepositoriesService } from "@/client"
import PendingItems from "@/components/Pending/PendingItems"

export const Route = createFileRoute("/_layout/$owner/$repo/")({
  component: RepositoryIndexRedirect,
})

function RepositoryIndexRedirect() {
  const { owner, repo } = Route.useParams()
  const repoPath = owner === "_" ? `${repo}.git` : `${owner}/${repo}.git`

  const { data } = useQuery({
    queryKey: ["repoInfo", repoPath],
    queryFn: async () => (await RepositoriesService.getRepositoryInfo({ path: { owner, repo } })).data,
  })

  if (!data) {
    return <PendingItems />
  }

  return (
    <Navigate to="/$owner/$repo/src/branch/$branch" params={{ owner, repo, branch: data.default_branch }} replace />
  )
}
