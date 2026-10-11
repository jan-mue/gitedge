import type { ComponentProps } from "react"
import { Input as PrimitiveInput } from "@/components/ui/input"
import { Label as PrimitiveLabel } from "@/components/ui/label"
import { PasswordInput as PrimitivePasswordInput } from "@/components/ui/password-input"
import { cn } from "@/lib/utils"
import { component } from "./component"

export const Input = component(PrimitiveInput, {
  search: "pl-9 bg-secondary",
  title: "h-10 text-lg font-bold",
  clone: "h-8 rounded-r-none bg-secondary font-mono text-xs text-muted-foreground sm:w-72",
  compact: "h-8 text-xs",
})
export const PasswordInput = component(PrimitivePasswordInput, {})
export const Label = component(PrimitiveLabel, {
  inline: "inline-flex items-center gap-2 font-normal",
  field: "mb-1 block",
})
const fieldStyles =
  "w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground outline-none transition-colors focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/50 aria-invalid:border-destructive disabled:cursor-not-allowed disabled:opacity-50"
export const Textarea = (props: Omit<ComponentProps<"textarea">, "className" | "style">) => (
  <textarea {...props} className={cn(fieldStyles, "min-h-20 resize-y")} />
)
export const NativeSelect = ({
  compact,
  ...props
}: Omit<ComponentProps<"select">, "className" | "style"> & { compact?: boolean }) => (
  <select {...props} className={cn(fieldStyles, compact ? "h-8 w-auto py-1" : "h-9")} />
)
export const ChoiceInput = (props: Omit<ComponentProps<"input">, "className" | "style">) => (
  <input
    {...props}
    className="size-4 accent-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring disabled:opacity-50"
  />
)
