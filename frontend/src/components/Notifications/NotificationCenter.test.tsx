import { createMemoryHistory, createRootRoute, createRoute, createRouter, RouterProvider } from "@tanstack/react-router"
import { HttpResponse } from "msw"
import { describe, expect, test } from "vitest"
import type { NotificationPublic } from "@/client"
import { handleNotificationsListNotifications, handleNotificationsUpdateNotifications } from "@/client/msw.gen"
import { server } from "@/test/server"
import { render, screen, waitFor } from "@/test/test-utils"
import { NotificationCenter } from "./NotificationCenter"
import { NotificationReturnBanner } from "./NotificationReturnBanner"
import { notificationOriginSchema, notificationSearchSchema } from "./search"

const notification: NotificationPublic = {
  id: "e922ae00-b2c3-4d21-a663-6ba206dddc00",
  repo_id: "00000000-0000-4000-a000-000000000002",
  repo: "owner/demo",
  number: 12,
  title: "A real notification",
  kind: "comment",
  category: "issue",
  reason: "author",
  actor: "alice",
  url: "/owner/demo/issues/12#comment-123",
  created_at: "2026-10-15T12:00:00Z",
  is_read: false,
  is_archived: false,
  unsubscribed: false,
}

const setup = (initial = "/notifications") => {
  let entry = { ...notification }
  server.use(
    handleNotificationsListNotifications(({ request }) => {
      const params = new URL(request.url).searchParams
      const included =
        entry.is_archived === (params.get("view") === "archived") &&
        (params.get("read") !== "unread" || !entry.is_read || params.get("focus") === entry.id)
      return HttpResponse.json({
        data: included ? [entry] : [],
        count: included ? 1 : 0,
        unread_count: entry.is_read || entry.is_archived ? 0 : 1,
        inbox_count: entry.is_archived ? 0 : 1,
        archived_count: entry.is_archived ? 1 : 0,
        repositories: included ? [entry.repo] : [],
        repository_counts: { [entry.repo]: 1 },
        reasons: { author: 1 },
      })
    }),
    handleNotificationsUpdateNotifications(async ({ request }) => {
      const { ids: _ids, ...changes } = await request.json()
      entry = {
        ...entry,
        is_read: changes.is_read ?? entry.is_read,
        is_archived: changes.is_archived ?? entry.is_archived,
        unsubscribed: changes.unsubscribed ?? entry.unsubscribed,
      }
      if (changes.is_archived) entry.is_read = true
      return new HttpResponse(null, { status: 204 })
    }),
  )
  const root = createRootRoute()
  const layout = createRoute({ getParentRoute: () => root, id: "_layout", validateSearch: notificationOriginSchema })
  const center = createRoute({
    getParentRoute: () => layout,
    path: "notifications",
    validateSearch: notificationSearchSchema,
    component: NotificationCenter,
  })
  const issue = createRoute({
    getParentRoute: () => layout,
    path: "$owner/$repo/issues/$number",
    component: NotificationReturnBanner,
  })
  const router = createRouter({
    routeTree: root.addChildren([layout.addChildren([center, issue])]),
    history: createMemoryHistory({ initialEntries: [initial] }),
  })
  return { ...render(<RouterProvider router={router} />), router }
}

describe("notification center", () => {
  test("opening a notification from email marks it read", async () => {
    const { user } = setup(`/owner/demo/issues/12?from=notifications&n=${notification.id}`)
    await user.click(await screen.findByRole("link", { name: "Back to notifications" }))
    expect(await screen.findByRole("button", { name: "Mark as unread" })).toBeInTheDocument()
  })

  test("returns from a discussion with filters and focused read entry preserved", async () => {
    const { user, router } = setup("/notifications?read=unread&query=real")
    await user.click(await screen.findByRole("link", { name: /A real notification #12/ }))
    expect(await screen.findByText("Opened from your notifications")).toBeInTheDocument()
    await user.click(screen.getByRole("link", { name: "Back to notifications" }))
    expect(await screen.findByRole("link", { name: /A real notification #12/ })).toBeInTheDocument()
    expect(screen.getByRole("textbox", { name: "Filter notifications" })).toHaveValue("real")
    expect(await screen.findByRole("button", { name: "Mark as unread" })).toBeInTheDocument()
    expect(router.state.location.search).toMatchObject({ read: "unread", query: "real", focus: notification.id })
  })

  test("archives and restores saved notifications", async () => {
    const { user } = setup()
    await user.click(await screen.findByRole("button", { name: "Dismiss" }))
    await waitFor(() => expect(screen.queryByRole("link", { name: /A real notification #12/ })).not.toBeInTheDocument())
    await user.click(screen.getAllByRole("button", { name: /Archived/ })[0])
    expect(await screen.findByRole("link", { name: /A real notification #12/ })).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Restore" }))
    await waitFor(() => expect(screen.queryByRole("link", { name: /A real notification #12/ })).not.toBeInTheDocument())
    await user.click(screen.getAllByRole("button", { name: /Inbox/ })[0])
    expect(await screen.findByRole("link", { name: /A real notification #12/ })).toBeInTheDocument()
  })
})
