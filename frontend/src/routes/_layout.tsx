import { createFileRoute, Outlet, redirect } from "@tanstack/react-router"
import GlobalNav from "@/components/GlobalNav"
import { AppShell } from "@/design-system"
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
    <AppShell>
      <GlobalNav />
      <Outlet />
    </AppShell>
  )
}
