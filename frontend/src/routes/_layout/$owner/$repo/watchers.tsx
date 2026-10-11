import { createFileRoute } from "@tanstack/react-router"
import RepositoryLayout from "@/components/Repositories/RepositoryLayout"
import Watchers from "@/components/Repository/Watchers"
import { Section } from "@/design-system"

export const Route = createFileRoute("/_layout/$owner/$repo/watchers")({
  component: WatchersPage,
  head: ({ params }) => ({
    meta: [{ title: `Watchers - ${params.owner}/${params.repo} - GitEdge` }],
  }),
})

function WatchersPage() {
  const { owner, repo } = Route.useParams()
  return (
    <RepositoryLayout owner={owner} repo={repo}>
      <Section title="Watchers">
        <Watchers owner={owner} repo={repo} />
      </Section>
    </RepositoryLayout>
  )
}
