import { createFileRoute, Outlet } from "@tanstack/react-router"

import RepositoryLayout from "@/components/Repositories/RepositoryLayout"

export const Route = createFileRoute("/_layout/$owner/$repo/commit")({
  component: CommitLayout,
})

function CommitLayout() {
  const { owner, repo } = Route.useParams()

  return (
    <RepositoryLayout owner={owner} repo={repo}>
      <Outlet />
    </RepositoryLayout>
  )
}
