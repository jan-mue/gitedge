import { HttpResponse } from "msw"
import {
  handleNotificationsGetRepositoryPreferences,
  handleNotificationsSetRepositoryPreferences,
} from "@/client/msw.gen"

export const notificationPreferenceHandlers = () => {
  let categories = ["pull", "issue", "release", "mention", "repository"]
  return [
    handleNotificationsGetRepositoryPreferences(() => HttpResponse.json({ categories })),
    handleNotificationsSetRepositoryPreferences(async ({ request }) => {
      categories = (await request.json()).categories ?? []
      return HttpResponse.json({ categories })
    }),
  ]
}
