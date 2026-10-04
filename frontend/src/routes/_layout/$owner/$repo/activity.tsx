import { createFileRoute } from "@tanstack/react-router"

import RepositoryLayout from "@/components/Repositories/RepositoryLayout"
import RepositoryActivity from "@/components/Repository/RepositoryActivity"

export const Route = createFileRoute("/_layout/$owner/$repo/activity")({
  component: ActivityPage,
  head: ({ params }) => ({
    meta: [{ title: `Activity - ${params.owner}/${params.repo} - GitEdge` }],
  }),
})

function ActivityPage() {
  const { owner, repo } = Route.useParams()
  return (
    <RepositoryLayout owner={owner} repo={repo}>
      <div className="space-y-4">
        <h1 className="text-lg font-semibold text-foreground">Activity</h1>
        <RepositoryActivity owner={owner} repo={repo} />
      </div>
    </RepositoryLayout>
  )
}
