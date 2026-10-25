import { createFileRoute } from "@tanstack/react-router"

import SourceView from "@/components/Repository/SourceView"

export const Route = createFileRoute("/_layout/$owner/$repo/src/tag/$tag/")({
  component: TagSourceRoot,
  head: ({ params }) => ({
    meta: [{ title: `${params.owner}/${params.repo} at ${params.tag} - GitEdge` }],
  }),
})

function TagSourceRoot() {
  const { owner, repo, tag } = Route.useParams()

  return <SourceView owner={owner} repo={repo} mode="tag" refName={tag} path="" />
}
