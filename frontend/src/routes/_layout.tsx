import { createFileRoute, Outlet, redirect } from "@tanstack/react-router"
import { AppShell } from "@/components/design-system"
import GlobalNav from "@/components/GlobalNav"
import { notificationOriginSchema } from "@/components/Notifications/search"
import { isLoggedIn } from "@/hooks/useAuth"

export const Route = createFileRoute("/_layout")({
  component: Layout,
  validateSearch: notificationOriginSchema,
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
