import { createFileRoute } from "@tanstack/react-router"
import { Star } from "lucide-react"

import RepositoryLayout from "@/components/Repositories/RepositoryLayout"
import Stargazers from "@/components/Repository/Stargazers"

export const Route = createFileRoute("/_layout/$owner/$repo/stars")({
  component: StargazersPage,
  head: ({ params }) => ({
    meta: [{ title: `Stargazers - ${params.owner}/${params.repo} - GitEdge` }],
  }),
})

function StargazersPage() {
  const { owner, repo } = Route.useParams()
  return (
    <RepositoryLayout owner={owner} repo={repo}>
      <div className="space-y-4">
        <h1 className="flex items-center gap-2 text-lg font-semibold text-foreground">
          <Star className="w-5 h-5" />
          Stargazers
        </h1>
        <Stargazers owner={owner} repo={repo} />
      </div>
    </RepositoryLayout>
  )
}
