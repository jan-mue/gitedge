import { createFileRoute } from "@tanstack/react-router"

import SourceView from "@/components/Repository/SourceView"

export const Route = createFileRoute("/_layout/$owner/$repo/src/branch/$branch/$")({
  component: BranchSourcePath,
})

function BranchSourcePath() {
  const { owner, repo, branch, _splat } = Route.useParams()

  return <SourceView owner={owner} repo={repo} mode="branch" refName={branch} path={_splat ?? ""} />
}
