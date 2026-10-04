import { createFileRoute } from "@tanstack/react-router"

import CommitsList from "@/components/Repository/CommitsList"

interface SearchParams {
  ref?: string
}

export const Route = createFileRoute("/_layout/$owner/$repo/commits/")({
  component: CommitsPage,
  validateSearch: (search: Record<string, unknown>): SearchParams => ({
    ref: (search.ref as string) || undefined,
  }),
  head: ({ params }) => ({
    meta: [{ title: `Commits - ${params.owner}/${params.repo} - GitEdge` }],
  }),
})

function CommitsPage() {
  const { owner, repo } = Route.useParams()
  const { ref } = Route.useSearch()

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-semibold text-foreground">Commit history</h1>
      <CommitsList owner={owner} repo={repo} searchRef={ref} />
    </div>
  )
}
