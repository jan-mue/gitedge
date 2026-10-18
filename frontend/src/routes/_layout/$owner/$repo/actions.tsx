import { createFileRoute } from "@tanstack/react-router"
import { z } from "zod"
import { RepositoryActions } from "@/components/Actions/RepositoryActions"
import RepositoryLayout from "@/components/Repositories/RepositoryLayout"

export const Route = createFileRoute("/_layout/$owner/$repo/actions")({
  validateSearch: z.object({ run: z.string().optional(), job: z.string().optional() }),
  component: ActionsPage,
  head: ({ params }) => ({ meta: [{ title: `Actions - ${params.owner}/${params.repo} - GitEdge` }] }),
})

function ActionsPage() {
  const { owner, repo } = Route.useParams()
  const { run, job } = Route.useSearch()
  const navigate = Route.useNavigate()
  return (
    <RepositoryLayout owner={owner} repo={repo}>
      <RepositoryActions
        key={`${owner}/${repo}`}
        owner={owner}
        repo={repo}
        runId={run}
        jobId={job}
        onSelectRun={(id) => navigate({ search: { run: id } })}
      />
    </RepositoryLayout>
  )
}
