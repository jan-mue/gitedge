import { createFileRoute } from "@tanstack/react-router"
import NewIssueForm from "@/components/Repository/NewIssueForm"
import { requireSession } from "@/lib/route-auth"

export const Route = createFileRoute("/_layout/$owner/$repo/issues/new")({
  beforeLoad: requireSession,
  component: NewIssue,
  head: ({ params }) => ({
    meta: [
      {
        title: `New Issue - ${params.owner}/${params.repo} - GitEdge`,
      },
    ],
  }),
})

function NewIssue() {
  const { owner, repo } = Route.useParams()

  return <NewIssueForm owner={owner} repo={repo} />
}
