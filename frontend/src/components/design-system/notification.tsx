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

/** Presentation only: links, selection, and mutations belong to the consumer. */
export const NotificationItem = ({
  unread = false,
  focused = false,
  selection,
  icon,
  actions,
  children,
  ...props
}: Omit<ComponentProps<"li">, "className" | "style" | "title"> & {
  unread?: boolean
  focused?: boolean
  selection: ReactNode
  icon: ReactNode
  actions?: ReactNode
}) => (
  <li
    {...props}
    className={`flex items-center gap-3 border-b border-border px-3 py-2 last:border-b-0 ${focused ? "ring-1 ring-inset ring-primary" : ""} ${unread ? "bg-primary/5" : ""}`}
  >
    {selection}
    <span aria-hidden="true" className={`size-2 shrink-0 rounded-full ${unread ? "bg-primary" : "bg-transparent"}`} />
    {unread && <span className="sr-only">Unread</span>}
    {icon}
    {children}
    <div className="flex shrink-0 items-center gap-0.5">{actions}</div>
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
    <div className="flex flex-wrap gap-x-2 text-xs text-muted-foreground">{children}</div>
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
