import { createFileRoute } from "@tanstack/react-router"
import NewPullRequestForm from "@/components/Repository/NewPullRequestForm"
import { requireSession } from "@/lib/route-auth"

export const Route = createFileRoute("/_layout/$owner/$repo/pulls/new")({
  beforeLoad: requireSession,
  component: NewPullRequest,
  head: ({ params }) => ({
    meta: [
      {
        title: `New Pull Request - ${params.owner}/${params.repo} - GitEdge`,
      },
    ],
  }),
})

function NewPullRequest() {
  const { owner, repo } = Route.useParams()

  return <NewPullRequestForm owner={owner} repo={repo} />
}
