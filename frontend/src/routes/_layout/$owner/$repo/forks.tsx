import { createFileRoute } from "@tanstack/react-router"
import { Section } from "@/components/design-system"
import RepositoryLayout from "@/components/Repositories/RepositoryLayout"
import { Forks } from "@/components/Repository/Forks"

export const Route = createFileRoute("/_layout/$owner/$repo/forks")({
  component: ForksPage,
  head: ({ params }) => ({
    meta: [{ title: `Forks - ${params.owner}/${params.repo} - GitEdge` }],
  }),
})

function ForksPage() {
  const { owner, repo } = Route.useParams()
  return (
    <RepositoryLayout owner={owner} repo={repo}>
      <Section title="Forks">
        <Forks owner={owner} repo={repo} />
      </Section>
    </RepositoryLayout>
  )
}
