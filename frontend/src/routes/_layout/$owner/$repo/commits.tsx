import { createFileRoute, Outlet } from "@tanstack/react-router"

import RepositoryLayout from "@/components/Repositories/RepositoryLayout"

export const Route = createFileRoute("/_layout/$owner/$repo/commits")({
  component: CommitsLayout,
})

function CommitsLayout() {
  const { owner, repo } = Route.useParams()

  return (
    <RepositoryLayout owner={owner} repo={repo}>
      <Outlet />
    </RepositoryLayout>
  )
}
