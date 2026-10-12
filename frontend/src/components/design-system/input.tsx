import { Input as PrimitiveInput } from "@/components/ui/input"
import { component } from "./component"
export const Input = component(
  PrimitiveInput,
  {
    search: "h-auto rounded border-border bg-secondary py-2 pl-9 text-sm",
    trackerSearch:
      "h-auto rounded border-border bg-secondary dark:bg-secondary px-3 py-1.5 text-sm focus-visible:border-border focus-visible:ring-1 focus-visible:ring-primary focus-visible:ring-offset-0",
    title: "h-10 text-lg font-bold md:text-lg",
    clone: "h-8 rounded-r-none bg-secondary font-mono text-xs text-muted-foreground sm:w-72 md:text-xs",
    compact: "h-8 text-xs md:text-xs",
    repository:
      "h-auto rounded border-border py-2 text-sm focus-visible:border-border focus-visible:ring-1 focus-visible:ring-primary focus-visible:ring-offset-0",
  },
  "h-10 rounded-md bg-background text-base shadow-none dark:bg-background focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background md:text-sm",
)
