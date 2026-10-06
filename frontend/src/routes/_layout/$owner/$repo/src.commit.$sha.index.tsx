import { createFileRoute } from "@tanstack/react-router"

import SourceView from "@/components/Repository/SourceView"

export const Route = createFileRoute("/_layout/$owner/$repo/src/commit/$sha/")({
  component: CommitSourceRoot,
  head: ({ params }) => ({
    meta: [{ title: `${params.owner}/${params.repo} at ${params.sha.slice(0, 10)} - GitEdge` }],
  }),
})

function CommitSourceRoot() {
  const { owner, repo, sha } = Route.useParams()

  return <SourceView owner={owner} repo={repo} mode="commit" refName={sha} path="" />
}
