import { createFileRoute, Outlet, redirect } from "@tanstack/react-router"

import GlobalNav from "@/components/GlobalNav"
import { isLoggedIn } from "@/hooks/useAuth"

export const Route = createFileRoute("/_layout")({
  component: Layout,
  beforeLoad: async () => {
    if (!isLoggedIn()) {
      throw redirect({
        to: "/login",
      })
    }
  },
})

function Layout() {
  return (
    <div className="min-h-screen bg-background">
      <GlobalNav />
      <Outlet />
    </div>
  )
}
