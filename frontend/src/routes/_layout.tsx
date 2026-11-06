import { createFileRoute, Outlet } from "@tanstack/react-router"
import { AppShell } from "@/components/design-system"
import GlobalNav from "@/components/GlobalNav"
import { notificationOriginSchema } from "@/components/Notifications/search"

export const Route = createFileRoute("/_layout")({
  component: Layout,
  validateSearch: notificationOriginSchema,
})

function Layout() {
  return (
    <AppShell>
      <GlobalNav />
      <Outlet />
    </AppShell>
  )
}
