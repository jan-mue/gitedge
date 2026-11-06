import { createFileRoute } from "@tanstack/react-router"
import { NotificationCenter } from "@/components/Notifications/NotificationCenter"
import { notificationSearchSchema } from "@/components/Notifications/search"
import { requireSession } from "@/lib/route-auth"

export const Route = createFileRoute("/_layout/notifications")({
  beforeLoad: requireSession,
  component: NotificationCenter,
  validateSearch: notificationSearchSchema,
  head: () => ({ meta: [{ title: "Notifications - GitEdge" }] }),
})
