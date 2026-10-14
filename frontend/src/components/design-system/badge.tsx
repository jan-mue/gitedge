import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"
import type { ComponentProps } from "react"

const badgeVariants = cva(
  "inline-flex w-fit shrink-0 items-center gap-1 whitespace-nowrap rounded-full border px-2.5 py-0.5 text-xs font-semibold [&_svg]:size-3",
  {
    variants: {
      variant: {
        default: "border-transparent bg-primary text-primary-foreground",
        secondary: "border-transparent bg-secondary text-secondary-foreground",
        outline: "border-border text-foreground",
        destructive: "border-transparent bg-destructive-emphasis text-destructive-foreground",
        success: "border-transparent bg-success-emphasis text-success-foreground",
        warning: "border-transparent bg-warning text-warning-foreground",
        info: "border-transparent bg-info-emphasis text-info-foreground",
        merged: "border-transparent bg-merged text-merged-foreground",
      },
    },
    defaultVariants: { variant: "default" },
  },
)
export const Badge = ({
  variant,
  asChild,
  ...props
}: Omit<ComponentProps<"span">, "className" | "style"> &
  VariantProps<typeof badgeVariants> & { asChild?: boolean }) => {
  const Comp = asChild ? Slot : "span"
  return <Comp {...props} data-slot="badge" className={badgeVariants({ variant })} />
}
