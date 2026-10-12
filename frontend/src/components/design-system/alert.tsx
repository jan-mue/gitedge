import type { ComponentProps } from "react"
import { cn } from "@/lib/utils"

export const Alert = ({
  variant = "default",
  ...props
}: Omit<ComponentProps<"div">, "className" | "style"> & { variant?: "default" | "destructive" }) => (
  <div
    {...props}
    role="alert"
    data-slot="alert"
    className={cn(
      "relative w-full rounded-lg border p-4 [&>svg~*]:pl-7 [&>svg+div]:-translate-y-0.5 [&>svg]:absolute [&>svg]:left-4 [&>svg]:top-4 [&>svg]:text-foreground",
      variant === "destructive"
        ? "border-destructive/50 text-destructive dark:border-destructive [&>svg]:text-destructive"
        : "bg-background text-foreground",
    )}
  />
)
export const AlertTitle = (props: Omit<ComponentProps<"h5">, "className" | "style">) => (
  <h5 {...props} data-slot="alert-title" className="mb-1 font-medium leading-none tracking-tight" />
)
export const AlertDescription = (props: Omit<ComponentProps<"div">, "className" | "style">) => (
  <div {...props} data-slot="alert-description" className="text-sm [&_p]:leading-relaxed" />
)
