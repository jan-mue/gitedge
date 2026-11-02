import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useSearch } from "@tanstack/react-router"
import { ArrowLeft, Inbox } from "lucide-react"
import { useEffect } from "react"
import {
  notificationsListNotificationsQueryKey,
  notificationsUpdateNotificationsMutation,
} from "@/client/@tanstack/react-query.gen"
import { Link, NotificationReturnNotice } from "@/components/design-system"
import { notificationSearchSchema } from "./search"

export const NotificationReturnBanner = () => {
  const search = useSearch({ strict: false })
  const queryClient = useQueryClient()
  const { mutate: markRead } = useMutation({
    ...notificationsUpdateNotificationsMutation(),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: notificationsListNotificationsQueryKey() }),
  })
  useEffect(() => {
    if (search.from === "notifications" && search.n && search.notification_query === undefined) {
      markRead({ body: { ids: [search.n], is_read: true } })
    }
  }, [search.from, search.n, search.notification_query, markRead])
  if (search.from !== "notifications") return null
  const saved = notificationSearchSchema.parse(Object.fromEntries(new URLSearchParams(search.notification_query)))
  return (
    <NotificationReturnNotice
      action={
        <Link to="/notifications" search={{ ...saved, focus: search.n }} appearance="notificationReturn">
          <ArrowLeft className="w-4 h-4" /> Back to notifications
        </Link>
      }
    >
      <Inbox className="w-4 h-4 shrink-0 text-primary" />
      <span className="truncate">Opened from your notifications</span>
    </NotificationReturnNotice>
  )
}
