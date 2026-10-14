export const signupsEnabled = import.meta.env.VITE_SIGNUPS_ENABLED !== "false"

function extractErrorMessage(err: unknown): string {
  const detail = (err as { detail?: unknown } | null)?.detail
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0] as { msg?: unknown }
    if (typeof first?.msg === "string") {
      return first.msg
    }
  }
  if (typeof detail === "string") {
    return detail
  }
  if (err instanceof Error) {
    return err.message
  }
  return "Something went wrong."
}

export const handleError = function (this: (msg: string) => void, err: unknown) {
  const errorMessage = extractErrorMessage(err)
  this(errorMessage)
}

export const getInitials = (name: string): string => {
  return name
    .split(" ")
    .slice(0, 2)
    .map((word) => word[0])
    .join("")
    .toUpperCase()
}

export const formatSize = (bytes: number): string => {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export const formatRelativeTime = (timestamp: number): string => {
  const minutes = Math.max(0, (Date.now() / 1000 - timestamp) / 60)
  if (minutes < 1) return "just now"
  const [unit, duration]: [string, number] =
    minutes < 60
      ? ["minute", 1]
      : minutes < 1440
        ? ["hour", 60]
        : minutes < 43200
          ? ["day", 1440]
          : minutes < 525600
            ? ["month", 43200]
            : ["year", 525600]
  const count = Math.floor(minutes / duration)
  return `${count} ${unit}${count === 1 ? "" : "s"} ago`
}
