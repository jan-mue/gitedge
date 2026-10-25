import { createFileRoute } from "@tanstack/react-router"
import { Section } from "@/components/design-system"
import { CommitsList } from "@/components/Repository/CommitsList"

export const Route = createFileRoute("/_layout/$owner/$repo/commits/tag/$tag")({
  validateSearch: (search: Record<string, unknown>): { path?: string } => ({
    path: typeof search.path === "string" ? search.path : undefined,
  }),
  component: TagCommitsPage,
  head: ({ params }) => ({
    meta: [{ title: `Commits on ${params.tag} - ${params.owner}/${params.repo} - GitEdge` }],
  }),
})

function TagCommitsPage() {
  const { owner, repo, tag } = Route.useParams()
  const { path } = Route.useSearch()

  return (
    <Section title="Commit history">
      <CommitsList owner={owner} repo={repo} tag={tag} filePath={path} />
    </Section>
  )
}
