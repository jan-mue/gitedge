import { MessageSquare } from "lucide-react"
import type { ReactNode } from "react"
import { formatRelativeTime } from "@/utils"
import "./conversation.css"

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
    className={`relative pb-6 sm:pl-14 before:absolute before:left-[19px] before:top-0 before:hidden before:w-0.5 before:bg-border sm:before:block ${
      terminal
        ? "before:h-[25px] after:absolute after:left-[19px] after:top-[25px] after:hidden after:h-0.5 after:w-[37px] after:bg-border sm:after:block"
        : "before:bottom-0"
    }`}
  >
    <div
      className={
        marker === "status"
          ? "absolute left-1 top-0 z-10 hidden size-8 items-center justify-center sm:flex"
          : `absolute left-1 ${terminal ? "top-[10px]" : "top-0.5"} z-10 hidden size-8 items-center justify-center rounded-full border border-border bg-secondary text-muted-foreground sm:flex`
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
  thread = false,
}: {
  author: string
  date: string
  badge?: string
  actions?: ReactNode
  children: ReactNode
  embedded?: boolean
  reply?: boolean
  thread?: boolean
}) => {
  const compact = reply || thread
  const renderAuthor = () => (
    <div className="flex min-w-0 items-center gap-2">
      <span
        aria-hidden="true"
        className={`flex shrink-0 items-center justify-center rounded-full bg-accent font-medium text-accent-foreground ${thread && !reply ? "size-6 text-xs" : "size-5 text-[10px]"}`}
      >
        {author.charAt(0).toUpperCase()}
      </span>
      <strong className="truncate text-sm font-medium">{author}</strong>
      {!compact && <span className="hidden text-xs text-muted-foreground sm:inline">commented</span>}
      <time dateTime={date} title={new Date(date).toLocaleString()} className="text-xs text-muted-foreground">
        {formatRelativeTime(new Date(date).getTime() / 1000)}
      </time>
    </div>
  )

  return (
    <article
      data-compact={compact || undefined}
      className={[
        "conversation-comment",
        embedded ? "overflow-hidden bg-card" : "overflow-hidden rounded-md border border-border bg-card",
        compact ? "px-3 py-2.5" : "",
      ].join(" ")}
    >
      <header
        className={`flex flex-wrap items-center justify-between gap-x-2 gap-y-1 ${compact ? "" : "border-b border-border bg-secondary/40 px-3 py-2"}`}
      >
        {renderAuthor()}
        <div className="flex items-center gap-2">
          {badge && (
            <span className="rounded border border-border px-1.5 text-[10px] leading-4 text-muted-foreground">
              {badge}
            </span>
          )}
          {actions}
        </div>
      </header>
      <div
        className={compact ? `${thread && !reply ? "pl-8 pt-1.5" : "pl-7 pt-1"} text-sm` : "px-3 py-3 text-sm sm:px-4"}
      >
        {children}
      </div>
    </article>
  )
}
