import { createFileRoute } from "@tanstack/react-router"

import { SourceView } from "@/components/Repository/SourceView"

export const Route = createFileRoute("/_layout/$owner/$repo/src/tag/$tag/$")({
  component: TagSourcePath,
})

function TagSourcePath() {
  const { owner, repo, tag, _splat } = Route.useParams()

  return <SourceView owner={owner} repo={repo} mode="tag" refName={tag} path={_splat ?? ""} />
}
