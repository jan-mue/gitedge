import { createFileRoute } from "@tanstack/react-router"

import PullRequestsList from "@/components/Repository/PullRequestsList"

export const Route = createFileRoute("/_layout/$owner/$repo/pulls/")({
  component: PullsIndex,
  head: ({ params }) => ({
    meta: [
      {
        title: `Pull Requests - ${params.owner}/${params.repo} - GitEdge`,
      },
    ],
  }),
})

function PullsIndex() {
  const { owner, repo } = Route.useParams()

  return <PullRequestsList owner={owner} repo={repo} />
}
