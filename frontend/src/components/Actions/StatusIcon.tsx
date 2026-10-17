import { CheckCircle, Clock, Loader2, MinusCircle, XCircle } from "lucide-react"
import type { ActionStatus } from "@/client"

export const StatusIcon = ({ status }: { status: ActionStatus }) => {
  const Icon =
    status === "success"
      ? CheckCircle
      : status === "failure"
        ? XCircle
        : status === "running"
          ? Loader2
          : status === "cancelled"
            ? MinusCircle
            : Clock
  const color =
    status === "success"
      ? "text-success"
      : status === "failure"
        ? "text-destructive"
        : status === "running"
          ? "text-warning animate-spin"
          : "text-muted-foreground"
  return (
    <span role="img" aria-label={status} className={`inline-flex shrink-0 ${color}`}>
      <Icon className="size-4" />
    </span>
  )
}

export const duration = (start?: string | null, end?: string | null) => {
  if (!start) return "—"
  const seconds = Math.max(
    0,
    Math.floor(((end ? new Date(end).getTime() : Date.now()) - new Date(start).getTime()) / 1000),
  )
  return seconds >= 60 ? `${Math.floor(seconds / 60)}m${seconds % 60}s` : `${seconds}s`
}
