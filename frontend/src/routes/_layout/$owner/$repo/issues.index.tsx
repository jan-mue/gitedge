import { createFileRoute } from "@tanstack/react-router"

import IssuesList from "@/components/Repository/IssuesList"

export const Route = createFileRoute("/_layout/$owner/$repo/issues/")({
  component: IssuesIndex,
  head: ({ params }) => ({
    meta: [
      {
        title: `Issues - ${params.owner}/${params.repo} - GitEdge`,
      },
    ],
  }),
})

function IssuesIndex() {
  const { owner, repo } = Route.useParams()

  return <IssuesList owner={owner} repo={repo} />
}
