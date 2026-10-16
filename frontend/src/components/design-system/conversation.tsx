import { MessageSquare } from "lucide-react"
import type { ReactNode } from "react"

export const ConversationTimeline = ({ children }: { children: ReactNode }) => (
  <div className="relative min-w-0 before:absolute before:bottom-0 before:left-[19px] before:top-0 before:hidden before:w-0.5 before:bg-border sm:before:block">
    {children}
  </div>
)

export const ConversationItem = ({
  children,
  icon = <MessageSquare className="size-2.5" />,
  marker = "comment",
}: {
  children: ReactNode
  icon?: ReactNode
  marker?: "comment" | "status"
}) => (
  <div className="relative pb-4 sm:pl-10">
    <div
      className={
        marker === "status"
          ? "absolute left-1 top-0 z-10 hidden size-8 items-center justify-center sm:flex"
          : "absolute left-[10px] top-4 z-10 hidden size-[19px] items-center justify-center rounded-full border-2 border-border bg-secondary text-muted-foreground sm:flex"
      }
    >
      {icon}
    </div>
    {children}
  </div>
)

export const ConversationCard = ({
  author,
  date,
  badge,
  actions,
  children,
}: {
  author: string
  date: string
  badge?: string
  actions?: ReactNode
  children: ReactNode
}) => (
  <article className="overflow-hidden rounded-lg border border-border bg-card">
    <header className="flex flex-wrap items-center justify-between gap-2 border-b border-border bg-secondary px-3 py-2.5 sm:px-4">
      <div className="flex min-w-0 items-center gap-2">
        <span
          aria-hidden="true"
          className="flex size-8 shrink-0 items-center justify-center rounded-full bg-accent text-sm font-medium text-accent-foreground"
        >
          {author.charAt(0).toUpperCase()}
        </span>
        <strong className="truncate text-sm font-medium">{author}</strong>
        <time dateTime={date} className="truncate text-xs text-muted-foreground">
          {new Date(date).toLocaleString()}
        </time>
      </div>
      <div className="flex items-center gap-2">
        {badge && (
          <span className="rounded border border-border px-2 py-0.5 text-xs text-muted-foreground">{badge}</span>
        )}
        {actions}
      </div>
    </header>
    <div className="px-4 py-4 text-sm">{children}</div>
  </article>
)
