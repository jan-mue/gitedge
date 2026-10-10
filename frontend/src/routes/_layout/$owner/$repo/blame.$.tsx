import { createFileRoute } from "@tanstack/react-router"
import RepositoryLayout from "@/components/Repositories/RepositoryLayout"
import BlameView from "@/components/Repository/BlameView"

export const Route = createFileRoute("/_layout/$owner/$repo/blame/$")({
  validateSearch: (search: Record<string, unknown>) => ({ ref: typeof search.ref === "string" ? search.ref : "HEAD" }),
  component: RepositoryBlame,
})
function RepositoryBlame() {
  const { owner, repo, _splat } = Route.useParams()
  const { ref } = Route.useSearch()
  return (
    <RepositoryLayout owner={owner} repo={repo}>
      <BlameView owner={owner} repo={repo} revision={ref} path={_splat ?? ""} />
    </RepositoryLayout>
  )
}
