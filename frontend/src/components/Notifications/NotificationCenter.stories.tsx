import type { Meta, StoryObj } from "@storybook/react-vite"
import { createMemoryHistory, createRootRoute, createRoute, createRouter, RouterProvider } from "@tanstack/react-router"
import { HttpResponse } from "msw"
import { useState } from "react"
import type { NotificationPublic } from "@/client"
import { handleNotificationsListNotifications, handleNotificationsUpdateNotifications } from "@/client/msw.gen"
import { notificationPreferenceHandlers } from "@/components/Storybook/notification-fixtures"
import { NotificationCenter } from "./NotificationCenter"
import { NotificationReturnBanner } from "./NotificationReturnBanner"
import { notificationOriginSchema, notificationSearchSchema } from "./search"

const entries = [
  ["gitedge/gitedge", 11192, "bug: Security vulnerability in GitEdge v14.0.2", "issue", "subscribed", 4],
  [
    "gitedge/gitedge",
    11190,
    "fix(#11189): normalize issue title case when matching prefixes",
    "pull",
    "participating",
    7,
  ],
  ["gitedge/gitedge", 11191, "@jan-mue can you reproduce the jumping buttons?", "mention", "mentioned", 9],
  ["gitedge/gitedge", null, "Repository activity (a1b2c3d)", "repository", "subscribed", 12],
  ["gitedge/gitedge", 11179, 'fix: improve SQLite "database is locked" errors', "pull", "author", 20],
  ["gitedge/docs", 2260, "feat(engine-core): add direct link to create issue for panic", "issue", "participating", 31],
  ["gitedge/docs", null, "Repository activity", "repository", "subscribed", 60],
  ["forgejo/forgejo", null, "Release v9.0.1 published", "release", "subscribed", 180],
  ["forgejo/forgejo", 5821, "Actions: runner labels not matched case-insensitively", "issue", "subscribed", 300],
] as const
const fixtures: NotificationPublic[] = entries.map(([repo, number, title, category, reason, minutes], index) => ({
  id: `00000000-0000-4000-a000-${String(index + 1).padStart(12, "0")}`,
  repo_id: "00000000-0000-4000-a000-000000000100",
  repo,
  number,
  title,
  category,
  reason,
  kind:
    category === "pull"
      ? "pull_request_open"
      : category === "release"
        ? "release"
        : category === "repository"
          ? "watch"
          : category === "mention"
            ? "comment"
            : "issue_open",
  actor: "alice",
  url: `/${repo}/issues/${number ?? 1}`,
  created_at: new Date(Date.now() - minutes * 60_000).toISOString(),
  is_read: index > 5,
  is_archived: false,
  unsubscribed: false,
}))
let notifications = fixtures.map((entry) => ({ ...entry }))
const NotificationStory = () => {
  const [router] = useState(() => {
    const root = createRootRoute()
    const layout = createRoute({ getParentRoute: () => root, id: "_layout", validateSearch: notificationOriginSchema })
    const center = createRoute({
      getParentRoute: () => layout,
      path: "notifications",
      validateSearch: notificationSearchSchema,
      component: NotificationCenter,
    })
    const discussion = createRoute({
      getParentRoute: () => layout,
      path: "$owner/$repo/issues/$number",
      component: NotificationReturnBanner,
    })
    return createRouter({
      routeTree: root.addChildren([layout.addChildren([center, discussion])]),
      history: createMemoryHistory({ initialEntries: ["/notifications"] }),
    })
  })
  return <RouterProvider router={router} />
}
const meta = {
  title: "Patterns/Notifications/Inbox",
  parameters: {
    layout: "fullscreen",
    msw: {
      handlers: [
        handleNotificationsListNotifications(({ request }) => {
          const params = new URL(request.url).searchParams
          const base = notifications.filter((entry) => entry.is_archived === (params.get("view") === "archived"))
          const visible = base.filter(
            (entry) =>
              (!params.get("reason") || entry.reason === params.get("reason")) &&
              (!params.get("repo") || entry.repo === params.get("repo")) &&
              (params.get("read") !== "unread" || !entry.is_read || params.get("focus") === entry.id) &&
              (!params.get("query") || entry.title.toLowerCase().includes(params.get("query")?.toLowerCase() ?? "")),
          )
          return HttpResponse.json({
            data: visible,
            count: visible.length,
            inbox_count: notifications.filter((entry) => !entry.is_archived).length,
            archived_count: notifications.filter((entry) => entry.is_archived).length,
            unread_count: notifications.filter((entry) => !entry.is_read && !entry.is_archived).length,
            repositories: [...new Set(base.map((entry) => entry.repo))],
            reasons: Object.fromEntries(
              base.map((entry) => [entry.reason, base.filter((other) => other.reason === entry.reason).length]),
            ),
            repository_counts: Object.fromEntries(
              base.map((entry) => [entry.repo, base.filter((other) => other.repo === entry.repo).length]),
            ),
          })
        }),
        ...notificationPreferenceHandlers(),
        handleNotificationsUpdateNotifications(async ({ request }) => {
          const { ids, ...changes } = await request.json()
          notifications = notifications.map((entry) =>
            ids.includes(entry.id)
              ? {
                  ...entry,
                  is_read: changes.is_read ?? entry.is_read,
                  is_archived: changes.is_archived ?? entry.is_archived,
                  unsubscribed: changes.unsubscribed ?? entry.unsubscribed,
                }
              : entry,
          )
          return HttpResponse.json({ data: [], count: 0 })
        }),
      ],
    },
  },
  beforeEach: () => {
    notifications = fixtures.map((entry) => ({ ...entry }))
  },
  render: () => <NotificationStory />,
} satisfies Meta
export default meta
type Story = StoryObj<typeof meta>
export const Inbox: Story = {}
export const Empty: Story = {
  beforeEach: () => {
    notifications = []
  },
}
