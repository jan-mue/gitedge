import { z } from "zod"

export const signupsEnabled = import.meta.env.VITE_SIGNUPS_ENABLED !== "false"

export function extractErrorMessage(err: unknown): string {
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

export const passwordSchema = z
  .string()
  .min(1, { message: "Password is required" })
  .min(8, { message: "Password must be at least 8 characters" })

export const passwordConfirmationSchema = z.object({
  new_password: passwordSchema,
  confirm_password: z.string().min(1, { message: "Password confirmation is required" }),
})

export const matchingPasswords = (data: { new_password: string; confirm_password: string }) =>
  data.new_password === data.confirm_password

export const passwordMismatch = { message: "The passwords don't match", path: ["confirm_password"] }
