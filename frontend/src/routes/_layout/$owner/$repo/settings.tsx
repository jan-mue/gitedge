import { createFileRoute } from "@tanstack/react-router"
import RepositoryLayout from "@/components/Repositories/RepositoryLayout"
import RepositorySettings from "@/components/Repository/RepositorySettings"
import { requireSession } from "@/lib/route-auth"

export const Route = createFileRoute("/_layout/$owner/$repo/settings")({
  beforeLoad: requireSession,
  component: RepositorySettingsPage,
})
function RepositorySettingsPage() {
  const { owner, repo } = Route.useParams()
  return (
    <RepositoryLayout owner={owner} repo={repo}>
      <RepositorySettings owner={owner} repo={repo} />
    </RepositoryLayout>
  )
}
