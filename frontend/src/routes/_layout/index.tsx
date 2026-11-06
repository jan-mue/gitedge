import { createFileRoute } from "@tanstack/react-router"
import Feed from "@/components/Dashboard/Feed"
import { requireSession } from "@/lib/route-auth"

export const Route = createFileRoute("/_layout/")({
  beforeLoad: requireSession,
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
