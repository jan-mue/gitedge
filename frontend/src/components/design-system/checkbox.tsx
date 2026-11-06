import { Checkbox as PrimitiveCheckbox } from "@/components/ui/checkbox"
import { component } from "./component"
export const Checkbox = component(
  PrimitiveCheckbox,
  { access: "size-5 rounded-md border-muted-foreground" },
  "rounded-sm border-primary bg-transparent shadow-none dark:bg-transparent focus-visible:border-primary focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background [&_svg]:size-4",
)
