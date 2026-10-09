import { createFileRoute } from "@tanstack/react-router"

import RepoExplorer from "@/components/Explore/RepoExplorer"

export const Route = createFileRoute("/_layout/explore")({
  component: ExplorePage,
  head: () => ({
    meta: [{ title: "Explore - GitEdge" }],
  }),
})

function ExplorePage() {
  return <RepoExplorer />
}
