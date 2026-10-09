import { createFileRoute } from "@tanstack/react-router"

import SourceView from "@/components/Repository/SourceView"

export const Route = createFileRoute("/_layout/$owner/$repo/src/branch/$branch/")({
  component: BranchSourceRoot,
  head: ({ params }) => ({
    meta: [{ title: `${params.owner}/${params.repo} at ${params.branch} - GitEdge` }],
  }),
})

function BranchSourceRoot() {
  const { owner, repo, branch } = Route.useParams()

  return <SourceView owner={owner} repo={repo} mode="branch" refName={branch} path="" />
}
