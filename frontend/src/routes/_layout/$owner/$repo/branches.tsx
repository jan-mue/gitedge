import { createFileRoute } from "@tanstack/react-router"
import { Section } from "@/components/design-system"
import RepositoryLayout from "@/components/Repositories/RepositoryLayout"
import BranchesList from "@/components/Repository/BranchesList"

export const Route = createFileRoute("/_layout/$owner/$repo/branches")({
  component: BranchesPage,
  head: ({ params }) => ({
    meta: [{ title: `Branches - ${params.owner}/${params.repo} - GitEdge` }],
  }),
})

function BranchesPage() {
  const { owner, repo } = Route.useParams()
  return (
    <RepositoryLayout owner={owner} repo={repo}>
      <Section title="Branches and tags">
        <BranchesList owner={owner} repo={repo} />
      </Section>
    </RepositoryLayout>
  )
}
