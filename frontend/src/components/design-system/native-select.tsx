import type { ComponentProps } from "react"
import { cn } from "@/lib/utils"
import { fieldStyles } from "./field-styles"
export const NativeSelect = ({
  compact,
  appearance,
  ...props
}: Omit<ComponentProps<"select">, "className" | "style"> & { compact?: boolean; appearance?: "owner" }) => (
  <select
    {...props}
    className={cn(
      fieldStyles,
      compact ? "h-8 w-auto py-1" : "h-auto",
      appearance === "owner" && "border-border bg-secondary",
    )}
  />
)
