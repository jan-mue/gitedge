import * as Primitive from "@radix-ui/react-popover"
import type { ComponentProps } from "react"
import { component } from "./component"

export const Popover = component(Primitive.Root, {})
export const PopoverTrigger = component(Primitive.Trigger, {})
export const PopoverClose = component(Primitive.Close, {})
const Content = component(
  Primitive.Content,
  { review: "w-[38rem] p-4" },
  "z-50 max-w-[calc(100vw-2rem)] max-h-[min(80vh,var(--radix-popover-content-available-height))] overflow-y-auto rounded-lg border border-border bg-popover p-3 text-popover-foreground shadow-xl outline-none data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:slide-in-from-top-1 motion-reduce:animate-none",
)
export const PopoverContent = (props: ComponentProps<typeof Content>) => (
  <Primitive.Portal>
    <Content align="end" sideOffset={8} collisionPadding={16} {...props} />
  </Primitive.Portal>
)
