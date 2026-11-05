import type { ComponentProps, ReactNode } from "react"

export const RepositoryMenuHeader = ({ children, muted = false }: { children: ReactNode; muted?: boolean }) => (
  <div
    className={`border-b border-border px-3 py-2 ${muted ? "text-xs font-medium text-muted-foreground" : "text-sm font-semibold"}`}
  >
    {children}
  </div>
)
export const RepositoryMenuFooter = ({ children }: { children: ReactNode }) => (
  <div className="border-t border-border px-3 py-2">{children}</div>
)
export const RepositoryMenuList = ({ children }: { children: ReactNode }) => (
  <div className="max-h-48 overflow-y-auto">{children}</div>
)
export const StarListOption = ({
  selected,
  count,
  children,
  ...props
}: Omit<ComponentProps<"button">, "className" | "style"> & { selected: boolean; count: number }) => (
  <button
    {...props}
    type="button"
    aria-pressed={selected}
    className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-foreground transition-colors hover:bg-accent focus-visible:outline-2 focus-visible:outline-ring disabled:opacity-50"
  >
    {children}
    <span className="ml-auto text-xs text-muted-foreground">{count}</span>
  </button>
)
