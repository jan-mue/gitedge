import { CheckCircle, Clock, Loader2, MinusCircle, XCircle } from "lucide-react"

export type CheckStatus = "queued" | "running" | "success" | "failure" | "skipped" | "cancelled"

export const CheckStatusIcon = ({ status }: { status: CheckStatus }) => {
  const Icon =
    status === "success"
      ? CheckCircle
      : status === "failure"
        ? XCircle
        : status === "running"
          ? Loader2
          : ["cancelled", "skipped"].includes(status)
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
