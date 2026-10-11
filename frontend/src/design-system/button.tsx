import { Slot, Slottable } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"
import { Loader2 } from "lucide-react"
import type { ComponentProps } from "react"
import { cn } from "@/lib/utils"

export const buttonVariants = cva(
  "inline-flex shrink-0 items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-colors outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:pointer-events-none disabled:opacity-50 [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground hover:bg-primary-hover",
        success: "bg-success-emphasis text-success-foreground hover:bg-success-hover",
        destructive: "bg-destructive-emphasis text-destructive-foreground hover:bg-destructive-hover",
        outline: "border border-border bg-secondary text-secondary-foreground hover:bg-accent",
        secondary: "bg-secondary text-secondary-foreground hover:bg-accent",
        ghost: "text-foreground hover:bg-accent",
        notification: "relative text-foreground hover:bg-accent",
        avatar: "rounded-full bg-primary text-primary-foreground hover:bg-primary-hover",
        link: "text-primary underline-offset-4 hover:underline",
        quiet:
          "text-muted-foreground hover:text-foreground hover:bg-accent aria-pressed:bg-accent aria-pressed:font-medium aria-pressed:text-foreground",
        tab: "rounded-none border-b-2 border-transparent text-muted-foreground hover:text-foreground aria-pressed:border-primary aria-pressed:text-foreground",
        row: "w-full justify-start rounded-none border-b border-border bg-card text-foreground hover:bg-accent/50 last:border-b-0",
        menu: "w-full justify-start rounded-none text-left text-foreground hover:bg-accent",
      },
      size: {
        default: "h-9 px-4 py-2",
        sm: "h-8 px-3 text-sm",
        xs: "h-7 px-2 text-xs",
        lg: "h-10 px-6",
        icon: "size-9 p-0",
        "icon-sm": "size-8 p-0",
        "icon-xs": "size-6 p-0",
        "icon-lg": "size-10 p-0",
      },
      shape: { default: "", start: "rounded-r-none border-r-0", end: "rounded-l-none", square: "rounded-none" },
      fullWidth: { true: "w-full", false: "" },
      visibility: { always: "", mobile: "md:hidden", desktop: "hidden md:inline-flex" },
      reveal: { true: "opacity-0 transition-opacity group-hover:opacity-100 focus-visible:opacity-100", false: "" },
    },
    defaultVariants: { variant: "default", size: "default", shape: "default" },
  },
)

type ButtonProps = Omit<ComponentProps<"button">, "className" | "style"> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean
    loading?: boolean
  }

export const Button = ({
  variant,
  size,
  shape,
  fullWidth,
  reveal,
  visibility,
  asChild,
  loading,
  disabled,
  children,
  ...props
}: ButtonProps) => {
  const Comp = asChild ? Slot : "button"
  return (
    <Comp
      {...props}
      type={asChild ? undefined : (props.type ?? "button")}
      data-slot="button"
      aria-busy={loading || undefined}
      disabled={loading || disabled}
      aria-disabled={asChild && (loading || disabled) ? true : undefined}
      tabIndex={asChild && (loading || disabled) ? -1 : props.tabIndex}
      onClick={asChild && (loading || disabled) ? (event) => event.preventDefault() : props.onClick}
      className={cn(buttonVariants({ variant, size, shape, fullWidth, reveal, visibility }))}
    >
      {loading && <Loader2 aria-hidden="true" className="size-4 animate-spin" />}
      <Slottable>{children}</Slottable>
    </Comp>
  )
}

export const LoadingButton = (props: ButtonProps) => <Button {...props} />
