import * as DialogPrimitive from "@radix-ui/react-dialog"
import { X } from "lucide-react"
import type { ComponentProps } from "react"
import {
  Dialog as PrimitiveDialog,
  DialogClose as PrimitiveDialogClose,
  DialogDescription as PrimitiveDialogDescription,
  DialogFooter as PrimitiveDialogFooter,
  DialogHeader as PrimitiveDialogHeader,
  DialogOverlay as PrimitiveDialogOverlay,
  DialogPortal as PrimitiveDialogPortal,
  DialogTitle as PrimitiveDialogTitle,
  DialogTrigger as PrimitiveDialogTrigger,
} from "@/components/ui/dialog"
import { cn } from "@/lib/utils"
import { component } from "./component"
export const Dialog = component(PrimitiveDialog, {})
export const DialogClose = component(PrimitiveDialogClose, {})
export const DialogContent = ({
  appearance,
  showCloseButton = true,
  children,
  ...props
}: Omit<ComponentProps<typeof DialogPrimitive.Content>, "className" | "style"> & {
  appearance?: "compact"
  showCloseButton?: boolean
}) => (
  <DialogPrimitive.Portal>
    <DialogOverlay />
    <DialogPrimitive.Content
      {...props}
      data-slot="dialog-content"
      className={cn(
        "fixed left-1/2 top-1/2 z-50 grid w-full max-w-lg -translate-x-1/2 -translate-y-1/2 gap-4 border border-border bg-background p-6 shadow-lg duration-200 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 sm:rounded-lg",
        appearance === "compact" && "sm:max-w-md",
      )}
    >
      {children}
      {showCloseButton && (
        <DialogPrimitive.Close className="absolute right-4 top-4 rounded-sm opacity-70 transition-opacity hover:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:pointer-events-none">
          <X className="size-4" />
          <span className="sr-only">Close</span>
        </DialogPrimitive.Close>
      )}
    </DialogPrimitive.Content>
  </DialogPrimitive.Portal>
)
export const DialogDescription = component(PrimitiveDialogDescription, {})
export const DialogFooter = component(PrimitiveDialogFooter, { spaced: "mt-4" })
export const DialogHeader = component(PrimitiveDialogHeader, {})
export const DialogOverlay = component(PrimitiveDialogOverlay, {}, "bg-overlay")
export const DialogPortal = component(PrimitiveDialogPortal, {})
export const DialogTitle = component(PrimitiveDialogTitle, {})
export const DialogTrigger = component(PrimitiveDialogTrigger, {})
