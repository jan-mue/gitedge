import { createFileRoute } from "@tanstack/react-router"

import CommitDetail from "@/components/Repository/CommitDetail"

export const Route = createFileRoute("/_layout/$owner/$repo/commits/$hash")({
  component: CommitDetailPage,
  head: ({ params }) => ({
    meta: [{ title: `Commit ${params.hash.slice(0, 10)} - ${params.owner}/${params.repo} - GitEdge` }],
  }),
})

function CommitDetailPage() {
  return <CommitDetail />
}
