import type { LucideIcon } from "lucide-react"
import type { ComponentProps, ReactNode } from "react"
export const Page = (props: Omit<ComponentProps<"main">, "className" | "style">) => (
  <main {...props} className="container mx-auto flex max-w-7xl flex-col gap-6 px-4 py-6" />
)
export const AppShell = ({ children }: { children: ReactNode }) => (
  <div className="min-h-screen bg-background">{children}</div>
)
export const PageHeader = ({
  title,
  description,
  actions,
}: {
  title: string
  description?: string
  actions?: ReactNode
}) => (
  <div className="flex items-start justify-between gap-4">
    <div>
      <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
      {description && <p className="text-muted-foreground">{description}</p>}
    </div>
    {actions}
  </div>
)
export const Section = ({ title, children, icon: Icon }: { title: string; children: ReactNode; icon?: LucideIcon }) => (
  <section className="space-y-4">
    <h1 className="flex items-center gap-2 text-lg font-semibold text-foreground">
      {Icon && <Icon aria-hidden="true" className="size-5" />}
      {title}
    </h1>
    {children}
  </section>
)
export const EmptyState = ({
  title,
  description,
  icon: Icon,
  actions,
}: {
  title: string
  description?: string
  icon?: LucideIcon
  actions?: ReactNode
}) => (
  <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-border px-4 py-12 text-center">
    {Icon && <Icon aria-hidden="true" className="mb-3 size-10 text-muted-foreground" />}
    <h3 className="text-lg font-semibold">{title}</h3>
    {description && <p className="mt-1 max-w-md text-sm text-muted-foreground">{description}</p>}
    {actions && <div className="mt-4">{actions}</div>}
  </div>
)
export const AuthForm = (props: Omit<ComponentProps<"form">, "className" | "style">) => (
  <form {...props} className="flex flex-col gap-6" />
)
export const AuthHeading = ({ children }: { children: ReactNode }) => (
  <div className="flex flex-col items-center gap-2 text-center">{children}</div>
)
export const AuthTitle = ({ children }: { children: ReactNode }) => <h1 className="text-2xl font-bold">{children}</h1>
export const FieldStack = ({ children }: { children: ReactNode }) => <div className="grid gap-4">{children}</div>
export const AuthFooter = ({ children }: { children: ReactNode }) => (
  <div className="text-center text-sm">{children}</div>
)
export const Inline = ({ children }: { children: ReactNode }) => <div className="flex items-center">{children}</div>
export const SectionHeader = ({
  title,
  description,
  actions,
}: {
  title: string
  description?: string
  actions?: ReactNode
}) => (
  <div className="flex items-center justify-between gap-4">
    <div>
      <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
      {description && <p className="text-muted-foreground">{description}</p>}
    </div>
    {actions}
  </div>
)
