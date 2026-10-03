import { createFileRoute, Outlet } from "@tanstack/react-router"

import RepositoryLayout from "@/components/Repositories/RepositoryLayout"

export const Route = createFileRoute("/_layout/$owner/$repo/pulls")({
  component: PullsLayout,
})

function PullsLayout() {
  const { owner, repo } = Route.useParams()

  return (
    <RepositoryLayout owner={owner} repo={repo}>
      <Outlet />
    </RepositoryLayout>
  )
}
