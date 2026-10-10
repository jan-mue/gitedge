import { createFileRoute } from "@tanstack/react-router"

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
    <div className="space-y-4">
      <h1 className="text-lg font-semibold text-foreground">Commit history</h1>
      <CommitsList owner={owner} repo={repo} branch={branch} filePath={path} />
    </div>
  )
}
