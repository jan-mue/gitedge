import { Inbox } from "lucide-react"
import type { ComponentProps, ReactNode } from "react"
import { Button } from "./button"

/** A responsive filter with the same selected state on desktop and mobile. */
export const NotificationFilter = ({
  mobile = false,
  count,
  children,
  ...props
}: Omit<ComponentProps<typeof Button>, "variant" | "size"> & { mobile?: boolean; count?: number }) => (
  <Button
    {...props}
    variant={mobile ? "notificationChip" : "notificationSidebar"}
    size={mobile ? "notificationChip" : "notificationSidebar"}
  >
    <span className="flex min-w-0 items-center gap-2 truncate">{children}</span>
    {count !== undefined && <span className="text-xs">{count}</span>}
  </Button>
)

/** Repository heading, selection, and actions above a list of notifications. */
export const NotificationGroup = ({
  selection,
  title,
  actions,
  children,
}: {
  selection: ReactNode
  title: ReactNode
  actions?: ReactNode
  children: ReactNode
}) => (
  <section className="overflow-hidden rounded-md border border-border">
    <header className="sticky top-0 z-10 flex items-center justify-between gap-2 border-b border-border bg-secondary px-3 py-2">
      <span className="flex min-w-0 items-center gap-3">
        {selection}
        {title}
      </span>
      <div className="flex shrink-0 items-center gap-1">{actions}</div>
    </header>
    <ul>{children}</ul>
  </section>
)

/** Four data columns, with utility actions kept inside the time cell. */
export const NotificationItem = ({
  unread = false,
  selection,
  icon,
  event,
  actor,
  timestamp,
  actions,
  children,
  ...props
}: Omit<ComponentProps<"li">, "className" | "style" | "title"> & {
  unread?: boolean
  selection: ReactNode
  icon: ReactNode
  event: ReactNode
  actor: ReactNode
  timestamp: ReactNode
  actions?: ReactNode
}) => (
  <li
    {...props}
    className={`grid grid-cols-[minmax(0,1fr)_2rem_auto] items-center gap-x-3 gap-y-2 px-3 py-3 sm:grid-cols-[minmax(0,1fr)_8rem_2rem_7rem] ${unread ? "bg-primary/5" : ""}`}
  >
    <div data-notification-column="subject" className="col-span-3 flex min-w-0 items-center gap-3 sm:col-span-1">
      {selection}
      <span aria-hidden="true" className={`size-2 shrink-0 rounded-full ${unread ? "bg-primary" : "bg-transparent"}`} />
      {unread && <span className="sr-only">Unread</span>}
      {icon}
      {children}
    </div>
    <div data-notification-column="event" className="min-w-0 text-xs text-muted-foreground">
      {event}
    </div>
    <div data-notification-column="actor" className="flex justify-center">
      {actor}
    </div>
    <div data-notification-column="time" className="flex flex-col items-end gap-1 text-xs text-muted-foreground">
      {timestamp}
      {actions && <div className="flex items-center gap-0.5">{actions}</div>}
    </div>
  </li>
)

export const NotificationSummary = ({
  title,
  number,
  unread = false,
  children,
}: {
  title: string
  number?: number | null
  unread?: boolean
  children: ReactNode
}) => (
  <>
    <div className={`truncate text-sm text-foreground group-hover:text-primary ${unread ? "font-semibold" : ""}`}>
      {title} {number != null && <span className="font-normal text-muted-foreground">#{number}</span>}
    </div>
    <div className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">{children}</div>
  </>
)

export const NotificationToolbar = ({ children }: { children: ReactNode }) => (
  <div className="flex flex-wrap items-center gap-2 rounded-md border border-border bg-secondary px-3 py-2">
    {children}
  </div>
)

export const NotificationReturnNotice = ({ children, action }: { children: ReactNode; action: ReactNode }) => (
  <div className="flex items-center justify-between gap-3 rounded-md border border-primary/30 bg-primary/5 px-3 py-2 text-sm">
    <span className="flex min-w-0 items-center gap-2 text-muted-foreground">{children}</span>
    {action}
  </div>
)

export const NotificationPreferenceList = ({
  compact = false,
  children,
}: {
  compact?: boolean
  children: ReactNode
}) => <div className={compact ? "py-1" : "divide-y divide-border rounded-md border border-border"}>{children}</div>
export const NotificationPreferenceOption = ({
  compact = false,
  htmlFor,
  icon,
  label,
  children,
  ...props
}: Omit<ComponentProps<"label">, "className" | "style"> & { compact?: boolean; icon: ReactNode; label: string }) => (
  <label
    {...props}
    htmlFor={htmlFor}
    className={`flex cursor-pointer items-center justify-between gap-3 px-3 ${compact ? "py-1.5 hover:bg-accent" : "py-2.5"}`}
  >
    <span className="flex items-center gap-2 text-sm text-foreground">
      {icon}
      {label}
    </span>
    {children}
  </label>
)
export const NotificationEmptyState = ({ archived = false }: { archived?: boolean }) => (
  <div className="flex flex-col items-center rounded-md border border-border py-16 text-muted-foreground">
    <Inbox aria-hidden="true" className="mb-3 size-10" />
    <p className="text-sm">{archived ? "Nothing archived." : "No notifications match these filters."}</p>
  </div>
)
