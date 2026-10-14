import { Slot, Slottable } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"
import { Loader2 } from "lucide-react"
import type { ComponentProps } from "react"
import { cn } from "@/lib/utils"

export const buttonVariants = cva(
  "inline-flex shrink-0 items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-colors outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:pointer-events-none disabled:opacity-50 [&_svg]:shrink-0 [&_svg:not([class*='size-']):not([class*='h-']):not([class*='w-'])]:size-4",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground hover:bg-primary/90",
        success: "bg-success text-success-foreground hover:opacity-90",
        destructive: "bg-destructive text-destructive-foreground hover:bg-destructive/90",
        dangerOutline: "rounded border border-destructive text-destructive font-normal hover:bg-destructive/10",
        activity:
          "justify-start rounded text-left font-normal text-muted-foreground hover:text-foreground hover:bg-accent/50 aria-pressed:bg-accent aria-pressed:font-medium aria-pressed:text-foreground",
        filterMenu:
          "gap-1 font-normal text-muted-foreground hover:text-foreground data-[active=true]:font-medium data-[active=true]:text-foreground",
        outline: "border border-input bg-background hover:bg-accent hover:text-accent-foreground",
        repository: "gap-1.5 rounded border border-border bg-secondary text-foreground font-normal hover:bg-accent",
        create: "gap-1 rounded border border-border bg-background text-foreground font-normal hover:bg-accent",
        codeAction: "rounded border border-border bg-background text-xs font-normal hover:bg-accent",
        text: "text-xs font-normal text-muted-foreground hover:text-foreground",
        textDanger: "text-xs font-normal text-muted-foreground hover:text-destructive",
        readMore: "mt-2 font-medium underline underline-offset-2 hover:text-primary",
        filter:
          "font-normal text-muted-foreground hover:text-foreground aria-pressed:font-medium aria-pressed:text-foreground",
        mobileTabMenu:
          "gap-1 rounded-none border-b-2 border-transparent font-normal text-muted-foreground hover:text-foreground md:hidden",
        secondary: "bg-secondary text-secondary-foreground hover:bg-secondary/80",
        ghost: "text-foreground hover:bg-accent",
        notification: "relative text-foreground hover:bg-accent",
        avatar: "rounded-full bg-primary text-primary-foreground transition-opacity hover:opacity-90",
        link: "text-primary underline-offset-4 hover:underline",
        quiet:
          "font-normal text-muted-foreground hover:text-foreground hover:bg-accent aria-pressed:bg-accent aria-pressed:font-medium aria-pressed:text-foreground",
        tab: "rounded-none border-b-2 border-transparent font-normal text-muted-foreground hover:text-foreground aria-pressed:border-primary aria-pressed:font-medium aria-pressed:text-foreground",
        row: "w-full justify-start gap-3 rounded-none border-b border-border bg-background text-foreground font-normal hover:bg-accent/50 last:border-b-0 [&_[data-slot=file-name]:hover]:text-primary [&_[data-slot=file-name]:hover]:underline",
        fileRow:
          "grid w-full grid-cols-[minmax(0,1fr)_auto] gap-x-3 gap-y-1 rounded-none border-b border-border bg-background text-left text-foreground font-normal hover:bg-accent/50 last:border-b-0 sm:grid-cols-[12rem_minmax(0,1fr)_auto] [&_[data-slot=file-name]:hover]:text-primary [&_[data-slot=file-name]:hover]:underline",
        menu: "w-full justify-start rounded-none text-left font-normal text-foreground hover:bg-accent",
        branchItem: "w-full justify-start gap-2 rounded-none text-left font-normal text-foreground hover:bg-accent",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-9 px-3 text-sm",
        compact: "h-8 px-3 text-sm",
        branch: "h-auto px-3 py-1.5 text-sm",
        branchItem: "h-auto px-3 py-2 text-sm",
        create: "h-auto px-2 py-1",
        form: "h-auto px-4 py-2",
        activity: "h-auto px-3 py-2",
        danger: "h-auto px-3 py-2",
        code: "h-auto px-2.5 py-1 text-xs",
        text: "h-auto p-0",
        tab: "h-auto px-3 py-2.5",
        "file-row": "h-auto px-4 py-2 text-sm",
        xs: "h-7 px-2 text-xs",
        lg: "h-11 px-8",
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
