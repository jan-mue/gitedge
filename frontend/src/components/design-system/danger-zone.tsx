import type { ComponentProps, ReactNode } from "react"

type DangerZoneProps = Omit<ComponentProps<"section">, "className" | "style" | "title"> & { title?: ReactNode }

export const DangerZone = ({ title = "Danger zone", children, ...props }: DangerZoneProps) => (
  <section {...props} className="overflow-hidden rounded border border-destructive">
    <h3 className="border-b border-destructive bg-destructive/10 px-4 py-3 text-xl font-semibold text-destructive">
      {title}
    </h3>
    <div className="divide-y divide-border">{children}</div>
  </section>
)

export const DangerZoneAction = ({
  title,
  description,
  action,
}: {
  title: ReactNode
  description: ReactNode
  action: ReactNode
}) => (
  <div className="flex flex-col items-start gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
    <div className="min-w-0 flex-1">
      <p className="font-medium text-foreground">{title}</p>
      <div className="text-sm text-muted-foreground">{description}</div>
    </div>
    {action}
  </div>
)
