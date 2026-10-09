import { createFileRoute, Navigate } from "@tanstack/react-router"

interface SearchParams {
  ref?: string
}

export const Route = createFileRoute("/_layout/$owner/$repo/commits/")({
  component: CommitsIndexRedirect,
  validateSearch: (search: Record<string, unknown>): SearchParams => ({
    ref: (search.ref as string) || undefined,
  }),
})

function CommitsIndexRedirect() {
  const { owner, repo } = Route.useParams()
  const { ref } = Route.useSearch()

  return <Navigate to="/$owner/$repo/commits/branch/$branch" params={{ owner, repo, branch: ref ?? "main" }} replace />
}
