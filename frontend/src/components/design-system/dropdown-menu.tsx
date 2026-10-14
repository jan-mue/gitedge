import {
  DropdownMenu as PrimitiveDropdownMenu,
  DropdownMenuCheckboxItem as PrimitiveDropdownMenuCheckboxItem,
  DropdownMenuContent as PrimitiveDropdownMenuContent,
  DropdownMenuGroup as PrimitiveDropdownMenuGroup,
  DropdownMenuItem as PrimitiveDropdownMenuItem,
  DropdownMenuLabel as PrimitiveDropdownMenuLabel,
  DropdownMenuPortal as PrimitiveDropdownMenuPortal,
  DropdownMenuRadioGroup as PrimitiveDropdownMenuRadioGroup,
  DropdownMenuRadioItem as PrimitiveDropdownMenuRadioItem,
  DropdownMenuSeparator as PrimitiveDropdownMenuSeparator,
  DropdownMenuShortcut as PrimitiveDropdownMenuShortcut,
  DropdownMenuSub as PrimitiveDropdownMenuSub,
  DropdownMenuSubContent as PrimitiveDropdownMenuSubContent,
  DropdownMenuSubTrigger as PrimitiveDropdownMenuSubTrigger,
  DropdownMenuTrigger as PrimitiveDropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { component } from "./component"
export const DropdownMenu = component(PrimitiveDropdownMenu, {})
export const DropdownMenuPortal = component(PrimitiveDropdownMenuPortal, {})
export const DropdownMenuTrigger = component(PrimitiveDropdownMenuTrigger, {})
export const DropdownMenuContent = component(PrimitiveDropdownMenuContent, {
  create: "w-48",
  account: "w-52",
  filter: "w-56 max-h-72 overflow-y-auto rounded-lg",
})
export const DropdownMenuGroup = component(PrimitiveDropdownMenuGroup, {})
export const DropdownMenuItem = component(PrimitiveDropdownMenuItem, {
  destructive: "text-destructive focus:text-destructive",
})
export const DropdownMenuCheckboxItem = component(PrimitiveDropdownMenuCheckboxItem, {})
export const DropdownMenuRadioGroup = component(PrimitiveDropdownMenuRadioGroup, {})
export const DropdownMenuRadioItem = component(PrimitiveDropdownMenuRadioItem, {})
export const DropdownMenuLabel = component(PrimitiveDropdownMenuLabel, {})
export const DropdownMenuSeparator = component(PrimitiveDropdownMenuSeparator, {})
export const DropdownMenuShortcut = component(PrimitiveDropdownMenuShortcut, {})
export const DropdownMenuSub = component(PrimitiveDropdownMenuSub, {})
export const DropdownMenuSubTrigger = component(PrimitiveDropdownMenuSubTrigger, {})
export const DropdownMenuSubContent = component(PrimitiveDropdownMenuSubContent, {})
