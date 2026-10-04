import { createFileRoute } from "@tanstack/react-router"

import RepositoryLayout from "@/components/Repositories/RepositoryLayout"
import BranchesList from "@/components/Repository/BranchesList"

export const Route = createFileRoute("/_layout/$owner/$repo/branches")({
  component: BranchesPage,
  head: ({ params }) => ({
    meta: [{ title: `Branches - ${params.owner}/${params.repo} - GitEdge` }],
  }),
})

function BranchesPage() {
  const { owner, repo } = Route.useParams()
  return (
    <RepositoryLayout owner={owner} repo={repo}>
      <div className="space-y-4">
        <h1 className="text-lg font-semibold text-foreground">Branches and tags</h1>
        <BranchesList owner={owner} repo={repo} />
      </div>
    </RepositoryLayout>
  )
}
