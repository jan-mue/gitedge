import { createFileRoute } from "@tanstack/react-router"
import { Section } from "@/components/design-system"
import CommitsList from "@/components/Repository/CommitsList"

export const Route = createFileRoute("/_layout/$owner/$repo/commits/branch/$branch")({
  validateSearch: (search: Record<string, unknown>): { path?: string } => ({
    path: typeof search.path === "string" ? search.path : undefined,
  }),
  component: BranchCommitsPage,
  head: ({ params }) => ({
    meta: [{ title: `Commits on ${params.branch} - ${params.owner}/${params.repo} - GitEdge` }],
  }),
})

function BranchCommitsPage() {
  const { owner, repo, branch } = Route.useParams()
  const { path } = Route.useSearch()

  return (
    <Section title="Commit history">
      <CommitsList owner={owner} repo={repo} branch={branch} filePath={path} />
    </Section>
  )
}
