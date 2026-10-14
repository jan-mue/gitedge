import type { ComponentProps } from "react"
import { cn } from "@/lib/utils"
import { fieldStyles } from "./field-styles"
export const Textarea = ({
  appearance,
  ...props
}: Omit<ComponentProps<"textarea">, "className" | "style"> & { appearance?: "repository" }) => (
  <textarea
    {...props}
    className={cn(
      fieldStyles,
      "min-h-20 resize-y",
      appearance === "repository" &&
        "h-20 resize-none border-border focus-visible:border-border focus-visible:ring-1 focus-visible:ring-primary",
    )}
  />
)
