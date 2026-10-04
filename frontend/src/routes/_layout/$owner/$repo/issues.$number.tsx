import { createFileRoute } from "@tanstack/react-router"

import IssueDetail from "@/components/Repository/IssueDetail"

export const Route = createFileRoute("/_layout/$owner/$repo/issues/$number")({
  component: IssueDetailPage,
  head: ({ params }) => ({
    meta: [
      {
        title: `Issue #${params.number} - ${params.owner}/${params.repo} - GitEdge`,
      },
    ],
  }),
})

function IssueDetailPage() {
  return <IssueDetail />
}
