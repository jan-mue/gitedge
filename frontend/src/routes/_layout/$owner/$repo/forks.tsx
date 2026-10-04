import { createFileRoute } from "@tanstack/react-router"
import { GitFork } from "lucide-react"

import RepositoryLayout from "@/components/Repositories/RepositoryLayout"
import Forks from "@/components/Repository/Forks"

export const Route = createFileRoute("/_layout/$owner/$repo/forks")({
  component: ForksPage,
  head: ({ params }) => ({
    meta: [{ title: `Forks - ${params.owner}/${params.repo} - GitEdge` }],
  }),
})

function ForksPage() {
  const { owner, repo } = Route.useParams()
  return (
    <RepositoryLayout owner={owner} repo={repo}>
      <div className="space-y-4">
        <h1 className="flex items-center gap-2 text-lg font-semibold text-foreground">
          <GitFork className="w-5 h-5" />
          Forks
        </h1>
        <Forks owner={owner} repo={repo} />
      </div>
    </RepositoryLayout>
  )
}
