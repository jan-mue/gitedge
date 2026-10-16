import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useNavigate, useSearch } from "@tanstack/react-router"
import {
  Archive,
  ArchiveRestore,
  AtSign,
  Bell,
  BellOff,
  Check,
  CheckCheck,
  Inbox,
  MessageSquare,
  Pin,
  Settings2,
} from "lucide-react"
import { useEffect, useState } from "react"
import type { NotificationPublic, NotificationUpdate } from "@/client"
import {
  notificationsArchiveRepositoryMutation,
  notificationsListNotificationsOptions,
  notificationsListNotificationsQueryKey,
  notificationsMarkAllReadMutation,
  notificationsUpdateNotificationsMutation,
} from "@/client/@tanstack/react-query.gen"
import { Button, ChoiceInput, Input, Link, Page } from "@/components/design-system"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"
import { categoryMeta, RepositoryNotificationPreferences } from "./RepositoryNotificationPreferences"
import type { NotificationSearch } from "./search"

const reasons = [
  { id: "mentioned", label: "Mentioned", icon: AtSign },
  { id: "author", label: "Authored", icon: Pin },
  { id: "participating", label: "Participating", icon: MessageSquare },
  { id: "reaction", label: "Reactions", icon: Check },
  { id: "subscribed", label: "Watching", icon: Bell },
]
const PAGE_SIZE = 50
const relativeTime = new Intl.RelativeTimeFormat("en", { numeric: "auto" })
const timeAgo = (date: string) => {
  const minutes = Math.max(0, Math.floor((Date.now() - new Date(date).getTime()) / 60_000))
  if (minutes < 1) return "just now"
  if (minutes < 60) return relativeTime.format(-minutes, "minute")
  if (minutes < 1440) return relativeTime.format(-Math.floor(minutes / 60), "hour")
  return relativeTime.format(-Math.floor(minutes / 1440), "day")
}

export const NotificationCenter = () => {
  const search = useSearch({ from: "/_layout/notifications" })
  const navigate = useNavigate({ from: "/notifications" })
  const queryClient = useQueryClient()
  const { showErrorToast } = useCustomToast()
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [managing, setManaging] = useState<string | null>(null)
  const view = search.view ?? "inbox"
  const read = search.read ?? "all"
  const page = search.page ?? 0
  const { data, isPending, isError, refetch } = useQuery({
    ...notificationsListNotificationsOptions({
      query: {
        view,
        read,
        reason: search.reason,
        repo: search.repo,
        query: search.query,
        focus: search.focus,
        offset: page * PAGE_SIZE,
        limit: PAGE_SIZE,
      },
    }),
    refetchInterval: 30_000,
  })
  const totalCount = data?.count
  useEffect(() => {
    if (totalCount !== undefined && page > 0 && page * PAGE_SIZE >= totalCount) {
      navigate({
        search: (previous) => ({ ...previous, page: Math.max(0, Math.ceil(totalCount / PAGE_SIZE) - 1) || undefined }),
        replace: true,
      })
    }
  }, [totalCount, page, navigate])
  const invalidate = () => queryClient.invalidateQueries({ queryKey: notificationsListNotificationsQueryKey() })
  const onError = handleError.bind(showErrorToast)
  const update = useMutation({
    ...notificationsUpdateNotificationsMutation(),
    onSuccess: () => {
      setSelected(new Set())
      return invalidate()
    },
    onError,
  })
  const markAll = useMutation({ ...notificationsMarkAllReadMutation(), onSuccess: invalidate, onError })
  const clearRepository = useMutation({ ...notificationsArchiveRepositoryMutation(), onSuccess: invalidate, onError })
  const busy = update.isPending || markAll.isPending || clearRepository.isPending

  useEffect(() => {
    if (search.focus && data?.data.some((n) => n.id === search.focus))
      document.getElementById(`notif-${search.focus}`)?.scrollIntoView?.({ block: "center" })
  }, [search.focus, data])

  const setParam = <K extends keyof NotificationSearch>(key: K, value: NotificationSearch[K]) => {
    setSelected(new Set())
    navigate({
      search: { ...search, [key]: value, focus: undefined, page: key === "page" ? (value as number) : undefined },
      replace: true,
    })
  }
  const visible = data?.data ?? []
  const groups = visible.reduce<Record<string, NotificationPublic[]>>((result, n) => {
    result[n.repo] ??= []
    result[n.repo].push(n)
    return result
  }, {})
  const selectedVisible = visible.filter((n) => selected.has(n.id)).map((n) => n.id)
  const allSelected = visible.length > 0 && selectedVisible.length === visible.length
  const toggle = (ids: string[], force?: boolean) =>
    setSelected((previous) => {
      const next = new Set(previous)
      for (const id of ids) {
        if (force ?? !next.has(id)) next.add(id)
        else next.delete(id)
      }
      return next
    })
  const patch = (ids: string[], changes: Omit<NotificationUpdate, "ids">) =>
    update.mutate({ body: { ids, ...changes } })
  const bulk = (changes: Omit<NotificationUpdate, "ids">) => patch(selectedVisible, changes)
  const returnQuery = new URLSearchParams()
  for (const key of ["view", "read", "reason", "repo", "query", "page"] as const) {
    const value = search[key]
    if (value !== undefined) returnQuery.set(key, String(value))
  }
  const origin = (n: NotificationPublic) => ({
    from: "notifications" as const,
    n: n.id,
    notification_query: returnQuery.toString(),
  })

  const viewButtons = (mobile = false) => (
    <>
      {(["inbox", "archived"] as const).map((value) => (
        <Button
          key={value}
          variant={mobile ? "notificationChip" : "notificationSidebar"}
          size={mobile ? "notificationChip" : "notificationSidebar"}
          aria-pressed={view === value}
          onClick={() => setParam("view", value === "inbox" ? undefined : value)}
        >
          <span className="flex items-center gap-2">
            {value === "inbox" ? <Inbox className="w-4 h-4" /> : <Archive className="w-4 h-4" />}
            {value === "inbox" ? "Inbox" : "Archived"}
          </span>
          <span className="text-xs">{value === "inbox" ? (data?.inbox_count ?? 0) : (data?.archived_count ?? 0)}</span>
        </Button>
      ))}
    </>
  )
  return (
    <Page>
      <h1 className="sr-only">Notifications</h1>
      <div className="flex flex-col md:flex-row gap-4">
        <aside className="hidden md:block w-56 shrink-0 space-y-5" aria-label="Notification filters">
          <div className="space-y-1">{viewButtons()}</div>
          <div>
            <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider px-3 mb-1">Filters</div>
            {reasons.map((reason) => (
              <Button
                key={reason.id}
                variant="notificationSidebar"
                size="notificationSidebar"
                aria-pressed={search.reason === reason.id}
                onClick={() => setParam("reason", search.reason === reason.id ? undefined : reason.id)}
              >
                <span className="flex items-center gap-2">
                  <reason.icon className="w-4 h-4" />
                  {reason.label}
                </span>
                <span className="text-xs">{data?.reasons[reason.id] ?? 0}</span>
              </Button>
            ))}
          </div>
          <div>
            <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider px-3 mb-1">
              Repositories
            </div>
            {data?.repositories.map((repo) => (
              <Button
                key={repo}
                variant="notificationSidebar"
                size="notificationSidebar"
                aria-pressed={search.repo === repo}
                onClick={() => setParam("repo", search.repo === repo ? undefined : repo)}
              >
                <span className="truncate">{repo}</span>
                <span className="text-xs">{data.repository_counts[repo] ?? 0}</span>
              </Button>
            ))}
          </div>
          <Link to="/settings" search={{ tab: "notifications" }} appearance="muted">
            <Settings2 className="w-4 h-4" />
            Notification preferences
          </Link>
        </aside>
        <div className="flex-1 min-w-0 space-y-3">
          <nav className="md:hidden flex flex-wrap gap-1.5" aria-label="Notification filters">
            {viewButtons(true)}
            {reasons.map((reason) => (
              <Button
                key={reason.id}
                variant="notificationChip"
                size="notificationChip"
                aria-pressed={search.reason === reason.id}
                onClick={() => setParam("reason", search.reason === reason.id ? undefined : reason.id)}
              >
                {reason.label}
              </Button>
            ))}
            {data?.repositories.map((repo) => (
              <Button
                key={repo}
                variant="notificationChip"
                size="notificationChip"
                aria-pressed={search.repo === repo}
                onClick={() => setParam("repo", search.repo === repo ? undefined : repo)}
              >
                {repo}
              </Button>
            ))}
            <Link to="/settings" search={{ tab: "notifications" }} appearance="caption">
              Notification preferences
            </Link>
          </nav>
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex border border-border rounded overflow-hidden">
              {(["all", "unread"] as const).map((value) => (
                <Button
                  key={value}
                  variant="notificationTab"
                  size="notificationTab"
                  aria-pressed={read === value}
                  onClick={() => setParam("read", value === "all" ? undefined : value)}
                >
                  {value}
                </Button>
              ))}
            </div>
            <div className="flex-1 min-w-40">
              <Input
                appearance="notificationSearch"
                aria-label="Filter notifications"
                placeholder="Filter notifications"
                value={search.query ?? ""}
                onChange={(event) => setParam("query", event.target.value || undefined)}
              />
            </div>
            {view === "inbox" && (data?.unread_count ?? 0) > 0 && (
              <Button variant="repository" size="create" disabled={busy} onClick={() => markAll.mutate({})}>
                <CheckCheck className="w-4 h-4" />
                Mark all read
              </Button>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-2 px-3 py-2 border border-border rounded-md bg-secondary">
            <label
              htmlFor="select-notifications"
              className="flex items-center gap-2 text-sm text-muted-foreground cursor-pointer"
            >
              <ChoiceInput
                id="select-notifications"
                appearance="notification"
                type="checkbox"
                checked={allSelected}
                disabled={busy || !visible.length}
                onChange={() =>
                  toggle(
                    visible.map((n) => n.id),
                    !allSelected,
                  )
                }
              />
              {selectedVisible.length ? `${selectedVisible.length} selected` : "Select all"}
            </label>
            {selectedVisible.length > 0 && (
              <div className="flex flex-wrap gap-1.5 ml-auto">
                {view === "inbox" ? (
                  <>
                    <Button
                      variant="notificationAction"
                      size="notificationAction"
                      disabled={busy}
                      onClick={() => bulk({ is_read: true })}
                    >
                      <Check className="w-3.5 h-3.5" />
                      Mark read
                    </Button>
                    <Button
                      variant="notificationAction"
                      size="notificationAction"
                      disabled={busy}
                      onClick={() => bulk({ is_archived: true })}
                    >
                      <Archive className="w-3.5 h-3.5" />
                      Dismiss
                    </Button>
                  </>
                ) : (
                  <Button
                    variant="notificationAction"
                    size="notificationAction"
                    disabled={busy}
                    onClick={() => bulk({ is_archived: false })}
                  >
                    <ArchiveRestore className="w-3.5 h-3.5" />
                    Restore
                  </Button>
                )}
                <Button
                  variant="notificationAction"
                  size="notificationAction"
                  disabled={busy}
                  onClick={() => bulk({ unsubscribed: true })}
                >
                  <BellOff className="w-3.5 h-3.5" />
                  Unsubscribe
                </Button>
              </div>
            )}
          </div>
          {isPending && (
            <p role="status" className="py-16 text-center text-sm text-muted-foreground">
              Loading notifications…
            </p>
          )}
          {isError && (
            <div role="alert" className="py-12 text-center space-y-3">
              <p>Unable to load notifications.</p>
              <Button variant="repository" size="compact" onClick={() => refetch()}>
                Try again
              </Button>
            </div>
          )}
          {!isPending && !isError && visible.length === 0 && (
            <div className="flex flex-col items-center py-16 text-muted-foreground border border-border rounded-md">
              <Inbox className="w-10 h-10 mb-3" />
              <p className="text-sm">
                {view === "archived" ? "Nothing archived." : "No notifications match these filters."}
              </p>
            </div>
          )}
          {Object.entries(groups).map(([repo, items]) =>
            !items ? null : (
              <section key={repo} className="border border-border rounded-md overflow-hidden">
                <header className="sticky top-0 z-10 flex items-center justify-between gap-2 px-3 py-2 bg-secondary border-b border-border">
                  <span className="flex items-center gap-3 min-w-0">
                    <ChoiceInput
                      appearance="notification"
                      type="checkbox"
                      aria-label={`Select all in ${repo}`}
                      checked={items.every((n) => selected.has(n.id))}
                      disabled={busy}
                      onChange={() =>
                        toggle(
                          items.map((n) => n.id),
                          !items.every((n) => selected.has(n.id)),
                        )
                      }
                    />
                    <Link
                      to="/$owner/$repo"
                      params={{ owner: repo.split("/")[0], repo: repo.split("/")[1] }}
                      appearance="notificationRepository"
                    >
                      {repo}
                    </Link>
                  </span>
                  <div className="flex items-center gap-1 shrink-0">
                    <Button variant="notificationAction" size="notificationAction" onClick={() => setManaging(repo)}>
                      <Settings2 className="w-3.5 h-3.5" />
                      Manage
                    </Button>
                    {view !== "archived" && (
                      <Button
                        variant="notificationAction"
                        size="notificationAction"
                        disabled={busy}
                        onClick={() =>
                          clearRepository.mutate({ path: { owner: repo.split("/")[0], repo: repo.split("/")[1] } })
                        }
                      >
                        <Archive className="w-3.5 h-3.5" />
                        Clear
                      </Button>
                    )}
                  </div>
                </header>
                <ul>
                  {items.map((n) => {
                    const meta = categoryMeta[n.category]
                    const [path, hash] = n.url.split("#")
                    return (
                      <li
                        key={n.id}
                        id={`notif-${n.id}`}
                        className={`flex items-center gap-3 px-3 py-2 border-b border-border last:border-b-0 ${n.id === search.focus ? "ring-1 ring-inset ring-primary" : ""} ${!n.is_read ? "bg-primary/5" : ""}`}
                      >
                        <ChoiceInput
                          appearance="notification"
                          type="checkbox"
                          aria-label={`Select ${n.title}`}
                          checked={selected.has(n.id)}
                          disabled={busy}
                          onChange={() => toggle([n.id])}
                        />
                        <span
                          className={`w-2 h-2 rounded-full shrink-0 ${!n.is_read ? "bg-primary" : "bg-transparent"}`}
                        />
                        <meta.icon className={`w-4 h-4 shrink-0 ${meta.color}`} />
                        <Link
                          to={path}
                          hash={hash}
                          search={origin(n)}
                          appearance="notificationTarget"
                          onClick={() => {
                            if (!n.is_read) patch([n.id], { is_read: true })
                          }}
                        >
                          <div
                            className={`text-sm truncate group-hover:text-primary text-foreground ${!n.is_read ? "font-semibold" : ""}`}
                          >
                            {n.title}{" "}
                            {n.number != null && <span className="text-muted-foreground font-normal">#{n.number}</span>}
                          </div>
                          <div className="text-xs text-muted-foreground flex flex-wrap gap-x-2">
                            <span>{n.kind.replace(/_/g, " ")}</span>·<span>{n.reason}</span>·
                            <time dateTime={n.created_at} title={new Date(n.created_at).toLocaleString()}>
                              {timeAgo(n.created_at)}
                            </time>
                            {n.unsubscribed && <span className="text-warning">· unsubscribed from thread</span>}
                          </div>
                        </Link>
                        <div className="flex items-center gap-0.5 shrink-0">
                          {!n.is_archived && (
                            <Button
                              variant="notificationIcon"
                              size="notificationIcon"
                              disabled={busy}
                              aria-label={n.is_read ? "Mark as unread" : "Mark as read"}
                              title={n.is_read ? "Mark as unread" : "Mark as read"}
                              onClick={() => patch([n.id], { is_read: !n.is_read })}
                            >
                              {n.is_read ? <Pin className="w-4 h-4" /> : <Check className="w-4 h-4" />}
                            </Button>
                          )}
                          <Button
                            variant="notificationIcon"
                            size="notificationIcon"
                            disabled={busy}
                            aria-label={n.is_archived ? "Restore" : "Dismiss"}
                            title={n.is_archived ? "Restore" : "Dismiss (archive)"}
                            onClick={() => patch([n.id], { is_archived: !n.is_archived })}
                          >
                            {n.is_archived ? <ArchiveRestore className="w-4 h-4" /> : <Archive className="w-4 h-4" />}
                          </Button>
                          <Button
                            variant="notificationIcon"
                            size="notificationIcon"
                            disabled={busy}
                            aria-pressed={n.unsubscribed}
                            aria-label={n.unsubscribed ? "Resubscribe" : "Unsubscribe"}
                            title={n.unsubscribed ? "Resubscribe to thread" : "Unsubscribe from this thread"}
                            onClick={() => patch([n.id], { unsubscribed: !n.unsubscribed })}
                          >
                            {n.unsubscribed ? <Bell className="w-4 h-4" /> : <BellOff className="w-4 h-4" />}
                          </Button>
                        </div>
                      </li>
                    )
                  })}
                </ul>
              </section>
            ),
          )}
          {data && data.count > PAGE_SIZE && (
            <nav aria-label="Notification pages" className="flex items-center justify-between gap-3 text-sm">
              <Button
                variant="repository"
                size="compact"
                disabled={page === 0}
                onClick={() => setParam("page", page - 1)}
              >
                Previous
              </Button>
              <span>
                Page {page + 1} of {Math.ceil(data.count / PAGE_SIZE)}
              </span>
              <Button
                variant="repository"
                size="compact"
                disabled={(page + 1) * PAGE_SIZE >= data.count}
                onClick={() => setParam("page", page + 1)}
              >
                Next
              </Button>
            </nav>
          )}
          <p className="text-xs text-muted-foreground">
            <Archive className="inline w-3 h-3" /> Dismiss hides a notification (restore it from Archived).{" "}
            <BellOff className="inline w-3 h-3" /> Unsubscribe stops future updates for that thread. Use Manage to
            choose which kinds of notifications each repository sends.
          </p>
        </div>
      </div>
      {managing && <RepositoryNotificationPreferences repository={managing} onClose={() => setManaging(null)} />}
    </Page>
  )
}
