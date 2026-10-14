import { createFileRoute } from "@tanstack/react-router"
import { Section } from "@/components/design-system"
import RepositoryLayout from "@/components/Repositories/RepositoryLayout"
import Watchers from "@/components/Repository/Watchers"

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
