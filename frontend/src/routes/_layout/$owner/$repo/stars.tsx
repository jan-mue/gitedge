import { createFileRoute } from "@tanstack/react-router"
import RepositoryLayout from "@/components/Repositories/RepositoryLayout"
import Stargazers from "@/components/Repository/Stargazers"
import { Section } from "@/design-system"

export const Route = createFileRoute("/_layout/$owner/$repo/stars")({
  component: StargazersPage,
  head: ({ params }) => ({
    meta: [{ title: `Stargazers - ${params.owner}/${params.repo} - GitEdge` }],
  }),
})

function StargazersPage() {
  const { owner, repo } = Route.useParams()
  return (
    <RepositoryLayout owner={owner} repo={repo}>
      <Section title="Stargazers">
        <Stargazers owner={owner} repo={repo} />
      </Section>
    </RepositoryLayout>
  )
}
