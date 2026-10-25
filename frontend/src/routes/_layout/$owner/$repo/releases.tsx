import { createFileRoute } from "@tanstack/react-router"

import RepositoryLayout from "@/components/Repositories/RepositoryLayout"
import ReleasesList from "@/components/Repository/ReleasesList"

export const Route = createFileRoute("/_layout/$owner/$repo/releases")({
  component: ReleasesPage,
  head: ({ params }) => ({
    meta: [{ title: `Releases - ${params.owner}/${params.repo} - GitEdge` }],
  }),
})

function ReleasesPage() {
  const { owner, repo } = Route.useParams()
  return (
    <RepositoryLayout owner={owner} repo={repo}>
      <ReleasesList owner={owner} repo={repo} />
    </RepositoryLayout>
  )
}
