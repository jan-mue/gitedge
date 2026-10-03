import { createFileRoute } from "@tanstack/react-router"

import NewIssueForm from "@/components/Repository/NewIssueForm"

export const Route = createFileRoute("/_layout/$owner/$repo/issues/new")({
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
