import { createFileRoute } from "@tanstack/react-router"
import { NotificationCenter } from "@/components/Notifications/NotificationCenter"
import { notificationSearchSchema } from "@/components/Notifications/search"

export const Route = createFileRoute("/_layout/notifications")({
  component: NotificationCenter,
  validateSearch: notificationSearchSchema,
  head: () => ({ meta: [{ title: "Notifications - GitEdge" }] }),
})
