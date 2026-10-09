import { createFileRoute } from "@tanstack/react-router"
import { Eye } from "lucide-react"

import RepositoryLayout from "@/components/Repositories/RepositoryLayout"
import Watchers from "@/components/Repository/Watchers"

export const Route = createFileRoute("/_layout/$owner/$repo/watchers")({
  component: WatchersPage,
  head: ({ params }) => ({
    meta: [{ title: `Watchers - ${params.owner}/${params.repo} - GitEdge` }],
  }),
})

function WatchersPage() {
  const { owner, repo } = Route.useParams()
  return (
    <RepositoryLayout owner={owner} repo={repo}>
      <div className="space-y-4">
        <h1 className="flex items-center gap-2 text-lg font-semibold text-foreground">
          <Eye className="w-5 h-5" />
          Watchers
        </h1>
        <Watchers owner={owner} repo={repo} />
      </div>
    </RepositoryLayout>
  )
}
