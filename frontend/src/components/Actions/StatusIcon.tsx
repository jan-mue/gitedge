export { CheckStatusIcon as StatusIcon } from "@/components/design-system"

export const duration = (start?: string | null, end?: string | null) => {
  if (!start) return "—"
  const seconds = Math.max(
    0,
    Math.floor(((end ? new Date(end).getTime() : Date.now()) - new Date(start).getTime()) / 1000),
  )
  return seconds >= 60 ? `${Math.floor(seconds / 60)}m${seconds % 60}s` : `${seconds}s`
}
