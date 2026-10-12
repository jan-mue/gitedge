import { Input as PrimitiveInput } from "@/components/ui/input"
import { component } from "./component"
export const Input = component(
  PrimitiveInput,
  {
    search: "pl-9 bg-secondary",
    title: "h-10 text-lg font-bold",
    clone: "h-8 rounded-r-none bg-secondary font-mono text-xs text-muted-foreground sm:w-72",
    compact: "h-8 text-xs",
    repository:
      "h-auto rounded border-border py-2 focus-visible:border-border focus-visible:ring-1 focus-visible:ring-primary focus-visible:ring-offset-0",
  },
  "h-10 rounded-md bg-background text-sm shadow-none dark:bg-background focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
)
