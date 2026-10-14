import {
  Tooltip as PrimitiveTooltip,
  TooltipContent as PrimitiveTooltipContent,
  TooltipProvider as PrimitiveTooltipProvider,
  TooltipTrigger as PrimitiveTooltipTrigger,
} from "@/components/ui/tooltip"
import { component } from "./component"
export const Tooltip = component(PrimitiveTooltip, {})
export const TooltipTrigger = component(PrimitiveTooltipTrigger, {})
export const TooltipContent = component(
  PrimitiveTooltipContent,
  {},
  "border border-border bg-popover text-popover-foreground text-sm shadow-md [&_svg.rotate-45]:hidden",
)
export const TooltipProvider = component(PrimitiveTooltipProvider, {})
