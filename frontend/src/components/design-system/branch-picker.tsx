import * as Popover from "@radix-ui/react-popover"
import type { ComponentProps } from "react"
import { component } from "./component"

export const BranchPicker = component(Popover.Root, {})
export const BranchPickerTrigger = component(Popover.Trigger, {})
const Content = component(
  Popover.Content,
  {},
  "z-50 w-96 max-w-[calc(100vw-2rem)] rounded border border-border bg-popover text-popover-foreground shadow-lg outline-none",
)
export const BranchPickerContent = (props: Omit<ComponentProps<typeof Content>, "appearance">) => (
  <Popover.Portal>
    <Content align="start" sideOffset={4} collisionPadding={16} {...props} />
  </Popover.Portal>
)
