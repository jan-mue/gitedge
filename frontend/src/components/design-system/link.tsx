import { type LinkComponent, type LinkProps, Link as RouterLink } from "@tanstack/react-router"
import type { ComponentProps } from "react"
import { cn } from "@/lib/utils"

const appearances = {
  avatar:
    "flex size-8 shrink-0 items-center justify-center rounded-full bg-accent text-sm font-medium text-accent-foreground",
  author: "font-semibold hover:text-primary",
  strong: "font-semibold text-primary hover:underline",
  target: "hover:text-primary",
  preview: "mt-2 inline-block text-sm text-primary hover:underline",
  comments: "inline-flex items-center gap-1.5 hover:text-foreground",
  listRow: "block rounded px-2 py-2 transition-colors hover:bg-accent/50",
  body: "text-sm text-primary hover:underline",
  repositoryStrong: "text-sm font-semibold text-primary hover:underline",
  repository: "text-sm font-medium text-primary hover:underline",
  codeAction: "rounded border bg-background px-2.5 py-1 text-xs hover:bg-accent",
  repositoryEntry: "flex items-center gap-2 font-medium text-primary hover:underline",
  truncated: "min-w-0 truncate text-primary hover:underline",
  commitPreview: "block max-w-60 truncate text-xs hover:text-primary hover:underline",
  hash: "font-mono text-xs text-primary hover:underline",
  branch: "font-mono text-sm text-primary hover:underline",
  revision: "font-mono text-primary hover:underline",
  title: "text-sm font-medium text-foreground hover:text-primary",
  commitHash: "flex-shrink-0 font-mono text-xs text-primary hover:underline",
  successAction: "rounded bg-success px-4 py-2 text-sm font-medium text-success-foreground hover:opacity-90",
  trackerAction:
    "shrink-0 rounded bg-success px-4 py-1.5 text-sm font-medium text-success-foreground transition-opacity hover:opacity-90",
  formAction:
    "px-4 py-2 text-sm rounded border border-border bg-secondary text-foreground hover:bg-accent transition-colors",
  caption: "text-xs text-primary hover:underline",
  icon: "shrink-0",
  row: "flex items-center gap-2",
  item: "flex cursor-pointer items-center gap-2",
  default: "text-primary hover:underline",
  repositoryOwner: "text-foreground hover:text-primary hover:underline",
  repositoryName: "font-bold text-foreground hover:text-primary hover:underline",
  file: "text-foreground hover:text-primary hover:underline",
  muted: "inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground",
  underline: "text-sm underline underline-offset-4",
  recovery: "ml-auto text-sm underline-offset-4 hover:underline",
  action:
    "inline-flex h-8 items-center justify-center gap-2 rounded-md border border-border bg-secondary px-3 text-sm text-foreground hover:bg-accent",
  count:
    "inline-flex h-8 min-w-10 items-center justify-center rounded-r border border-border bg-secondary px-2.5 text-sm font-medium text-foreground hover:bg-accent",
  stat: "inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-primary",
  code: "rounded bg-accent px-1.5 py-0.5 font-mono text-xs text-primary hover:underline",
  brand: "flex items-center gap-2 text-foreground transition-colors hover:text-primary",
  tabDesktop:
    "hidden items-center gap-1.5 whitespace-nowrap border-b-2 border-transparent px-4 py-3 text-sm text-muted-foreground transition-colors hover:border-border hover:text-foreground data-[active=true]:border-primary data-[active=true]:font-medium data-[active=true]:text-foreground md:flex",
  tabMobile:
    "flex items-center gap-1 whitespace-nowrap border-b-2 border-transparent px-3 py-2.5 text-sm text-muted-foreground transition-colors hover:text-foreground data-[active=true]:border-primary data-[active=true]:font-medium data-[active=true]:text-foreground md:hidden",
  menu: "flex items-center gap-2 rounded px-3 py-2 text-sm text-foreground hover:bg-accent",
  social: "text-muted-foreground transition-colors hover:text-foreground",
  settings:
    "flex shrink-0 items-center gap-2 whitespace-nowrap rounded bg-accent/50 px-3 py-2 text-sm text-foreground transition-colors hover:bg-accent md:rounded-none md:border-b md:bg-transparent md:px-4 md:py-3",
  settingsDanger:
    "flex shrink-0 items-center gap-2 whitespace-nowrap rounded bg-accent/50 px-3 py-2 text-sm text-destructive transition-colors hover:bg-accent md:rounded-none md:bg-transparent md:px-4 md:py-3",
  inherited: "",
}
export type LinkAppearance = keyof typeof appearances

const Anchor = ({
  appearance = "default",
  active,
  ...props
}: Omit<ComponentProps<"a">, "className" | "style"> & { appearance?: keyof typeof appearances; active?: boolean }) => (
  <a
    {...props}
    data-active={active}
    className={cn(
      "outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
      appearances[appearance],
      (props as ComponentProps<"a">).className,
    )}
  />
)
export const Link = (({
  appearance = "default",
  active,
  ...props
}: Omit<ComponentProps<"a">, "className" | "style"> & { appearance?: keyof typeof appearances; active?: boolean }) => (
  <RouterLink
    {...(props as LinkProps)}
    data-active={active}
    className={cn(
      "outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
      appearances[appearance],
      (props as ComponentProps<"a">).className,
    )}
  />
)) as LinkComponent<typeof Anchor>

export const ExternalLink = Anchor
