import { createFileRoute } from "@tanstack/react-router"

import PullRequestDetail from "@/components/Repository/PullRequestDetail"

export const Route = createFileRoute("/_layout/$owner/$repo/pulls/$number")({
  component: PullRequestDetailPage,
  head: ({ params }) => ({
    meta: [
      {
        title: `Pull Request #${params.number} - ${params.owner}/${params.repo} - GitEdge`,
      },
    ],
  }),
})

function PullRequestDetailPage() {
  return <PullRequestDetail />
}
