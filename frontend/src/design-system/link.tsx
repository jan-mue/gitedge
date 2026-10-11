import { type LinkComponent, type LinkProps, Link as RouterLink } from "@tanstack/react-router"
import type { ComponentProps } from "react"
import { cn } from "@/lib/utils"

const appearances = {
  default: "text-primary hover:underline",
  muted: "inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground",
  underline: "text-sm underline underline-offset-4",
  recovery: "ml-auto text-sm underline-offset-4 hover:underline",
  action:
    "inline-flex h-8 items-center justify-center gap-2 rounded-md border border-border bg-secondary px-3 text-sm text-foreground hover:bg-accent",
  count:
    "inline-flex h-8 items-center justify-center rounded-r-md border border-border bg-secondary px-2.5 text-sm font-medium text-foreground hover:bg-accent",
  stat: "inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-primary",
  code: "rounded bg-accent px-1.5 py-0.5 font-mono text-xs text-primary hover:underline",
  brand: "flex items-center gap-2 text-foreground transition-colors hover:text-primary",
  tabDesktop:
    "hidden items-center gap-1.5 whitespace-nowrap border-b-2 border-transparent px-4 py-3 text-sm text-muted-foreground transition-colors hover:border-border hover:text-foreground data-[active=true]:border-primary data-[active=true]:font-medium data-[active=true]:text-foreground md:flex",
  tabMobile:
    "flex items-center gap-1 whitespace-nowrap border-b-2 border-transparent px-3 py-2.5 text-sm text-muted-foreground transition-colors hover:text-foreground data-[active=true]:border-primary data-[active=true]:font-medium data-[active=true]:text-foreground md:hidden",
  menu: "flex items-center gap-2 rounded px-3 py-2 text-sm text-foreground hover:bg-accent",
  inherited: "",
}
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
