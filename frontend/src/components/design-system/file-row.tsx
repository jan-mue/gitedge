import type { ComponentProps } from "react"

export const FileRow = (props: Omit<ComponentProps<"div">, "className" | "style">) => (
  <div
    {...props}
    className="grid w-full grid-cols-[minmax(0,1fr)_auto] gap-x-3 gap-y-1 border-b border-border bg-background px-4 py-2 text-left text-sm font-normal text-foreground hover:bg-accent/50 last:border-b-0 sm:grid-cols-[12rem_minmax(0,1fr)_auto]"
  />
)
