import { createFileRoute } from "@tanstack/react-router"

import SourceView from "@/components/Repository/SourceView"

export const Route = createFileRoute("/_layout/$owner/$repo/src/commit/$sha/$")({
  component: CommitSourcePath,
})

function CommitSourcePath() {
  const { owner, repo, sha, _splat } = Route.useParams()

  return <SourceView owner={owner} repo={repo} mode="commit" refName={sha} path={_splat ?? ""} />
}
