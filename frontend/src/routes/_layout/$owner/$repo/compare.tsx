import { createFileRoute } from "@tanstack/react-router"
import { z } from "zod"
import RepositoryLayout from "@/components/Repositories/RepositoryLayout"
import { CompareView } from "@/components/Repository/CompareView"

export const Route = createFileRoute("/_layout/$owner/$repo/compare")({
  component: ComparePage,
  validateSearch: z.object({ base: z.string().default("main"), head: z.string().default("HEAD") }),
  head: ({ params }) => ({ meta: [{ title: `Compare - ${params.owner}/${params.repo} - GitEdge` }] }),
})

function ComparePage() {
  const { owner, repo } = Route.useParams()
  const { base, head } = Route.useSearch()
  return (
    <RepositoryLayout owner={owner} repo={repo}>
      <CompareView key={`${base}/${head}`} />
    </RepositoryLayout>
  )
}
