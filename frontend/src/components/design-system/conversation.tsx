import { MessageSquare } from "lucide-react"
import type { ReactNode } from "react"

export const ConversationTimeline = ({ children }: { children: ReactNode }) => (
  <div className="relative min-w-0" data-testid="conversation-timeline">
    {children}
  </div>
)

export const ConversationItem = ({
  children,
  icon = <MessageSquare className="size-4 shrink-0" />,
  marker = "comment",
  terminal = false,
}: {
  children: ReactNode
  icon?: ReactNode
  marker?: "comment" | "status"
  terminal?: boolean
}) => (
  <div
    data-timeline-item={terminal ? "composer" : "event"}
    className={`relative pb-6 sm:pl-10 before:absolute before:left-[19px] before:top-0 before:hidden before:w-0.5 before:bg-border sm:before:block ${
      terminal
        ? "before:h-[25px] after:absolute after:left-[19px] after:top-[25px] after:hidden after:h-0.5 after:w-[21px] after:bg-border sm:after:block"
        : "before:bottom-0"
    }`}
  >
    <div
      className={
        marker === "status"
          ? "absolute left-1 top-0 z-10 hidden size-8 items-center justify-center sm:flex"
          : "absolute left-1 top-[10px] z-10 hidden size-8 items-center justify-center rounded-full border border-border bg-secondary text-muted-foreground sm:flex"
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
  embedded = false,
  reply = false,
}: {
  author: string
  date: string
  badge?: string
  actions?: ReactNode
  children: ReactNode
  embedded?: boolean
  reply?: boolean
}) => (
  <article
    className={
      embedded ? "overflow-hidden bg-card" : "overflow-hidden rounded-lg border border-border bg-card shadow-sm"
    }
  >
    <header
      className={`flex flex-wrap items-center justify-between gap-2 border-b border-border px-3 sm:px-4 ${reply ? "bg-secondary/50 py-2" : "bg-secondary py-2.5"}`}
    >
      <div className="flex min-w-0 items-center gap-2">
        <span
          aria-hidden="true"
          className={`flex shrink-0 items-center justify-center rounded-full bg-accent font-medium text-accent-foreground ${reply ? "size-6 text-xs" : "size-8 text-sm"}`}
        >
          {author.charAt(0).toUpperCase()}
        </span>
        <strong className="truncate text-sm font-medium">{author}</strong>
        <span className="hidden text-xs text-muted-foreground sm:inline">{reply ? "replied" : "commented"}</span>
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
    <div className={reply ? "px-4 py-3 text-sm sm:px-6" : "px-4 py-4 text-sm sm:px-6"}>{children}</div>
  </article>
)
