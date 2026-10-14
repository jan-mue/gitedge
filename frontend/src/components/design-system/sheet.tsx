import * as DialogPrimitive from "@radix-ui/react-dialog"
import { X } from "lucide-react"
import type { ComponentProps } from "react"
import {
  Sheet as PrimitiveSheet,
  SheetClose as PrimitiveSheetClose,
  SheetDescription as PrimitiveSheetDescription,
  SheetFooter as PrimitiveSheetFooter,
  SheetHeader as PrimitiveSheetHeader,
  SheetTitle as PrimitiveSheetTitle,
  SheetTrigger as PrimitiveSheetTrigger,
} from "@/components/ui/sheet"
import { cn } from "@/lib/utils"
import { component } from "./component"
import { DialogOverlay } from "./dialog"
export const Sheet = component(PrimitiveSheet, {})
export const SheetTrigger = component(PrimitiveSheetTrigger, {})
export const SheetClose = component(PrimitiveSheetClose, {})
const sides = {
  top: "inset-x-0 top-0 border-b data-[state=closed]:slide-out-to-top data-[state=open]:slide-in-from-top",
  bottom: "inset-x-0 bottom-0 border-t data-[state=closed]:slide-out-to-bottom data-[state=open]:slide-in-from-bottom",
  left: "inset-y-0 left-0 h-full w-3/4 border-r sm:max-w-sm data-[state=closed]:slide-out-to-left data-[state=open]:slide-in-from-left",
  right:
    "inset-y-0 right-0 h-full w-3/4 border-l sm:max-w-sm data-[state=closed]:slide-out-to-right data-[state=open]:slide-in-from-right",
}
export const SheetContent = ({
  side = "right",
  children,
  ...props
}: Omit<ComponentProps<typeof DialogPrimitive.Content>, "className" | "style"> & { side?: keyof typeof sides }) => (
  <DialogPrimitive.Portal>
    <DialogOverlay />
    <DialogPrimitive.Content
      {...props}
      data-slot="sheet-content"
      className={cn(
        "fixed z-50 gap-4 border-border bg-background p-6 shadow-lg transition-transform ease-in-out data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:duration-300 data-[state=open]:duration-500",
        sides[side],
      )}
    >
      {children}
      <DialogPrimitive.Close className="absolute right-4 top-4 rounded-sm opacity-70 transition-opacity hover:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background">
        <X className="size-4" />
        <span className="sr-only">Close</span>
      </DialogPrimitive.Close>
    </DialogPrimitive.Content>
  </DialogPrimitive.Portal>
)
export const SheetHeader = component(PrimitiveSheetHeader, {}, "space-y-2 gap-0 p-0 text-center sm:text-left")
export const SheetFooter = component(PrimitiveSheetFooter, {}, "mt-0 flex-col-reverse p-0 sm:flex-row sm:justify-end")
export const SheetTitle = component(PrimitiveSheetTitle, {}, "text-lg")
export const SheetDescription = component(PrimitiveSheetDescription, {})
