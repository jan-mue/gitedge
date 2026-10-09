import { createFileRoute } from "@tanstack/react-router"

import Feed from "@/components/Dashboard/Feed"

export const Route = createFileRoute("/_layout/")({
  component: Dashboard,
  head: () => ({
    meta: [
      {
        title: "Dashboard - GitEdge",
      },
    ],
  }),
})

function Dashboard() {
  return <Feed />
}
