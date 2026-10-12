import {
  Select as PrimitiveSelect,
  SelectContent as PrimitiveSelectContent,
  SelectGroup as PrimitiveSelectGroup,
  SelectItem as PrimitiveSelectItem,
  SelectLabel as PrimitiveSelectLabel,
  SelectScrollDownButton as PrimitiveSelectScrollDownButton,
  SelectScrollUpButton as PrimitiveSelectScrollUpButton,
  SelectSeparator as PrimitiveSelectSeparator,
  SelectTrigger as PrimitiveSelectTrigger,
  SelectValue as PrimitiveSelectValue,
} from "@/components/ui/select"
import { component } from "./component"
export const Select = component(PrimitiveSelect, {})
export const SelectContent = component(PrimitiveSelectContent, {})
export const SelectGroup = component(PrimitiveSelectGroup, {})
export const SelectItem = component(PrimitiveSelectItem, {})
export const SelectLabel = component(PrimitiveSelectLabel, {})
export const SelectScrollDownButton = component(PrimitiveSelectScrollDownButton, {})
export const SelectScrollUpButton = component(PrimitiveSelectScrollUpButton, {})
export const SelectSeparator = component(PrimitiveSelectSeparator, {})
export const SelectTrigger = component(
  PrimitiveSelectTrigger,
  { pagination: "h-8 w-20 data-[size=default]:h-8" },
  "w-full bg-background shadow-none dark:bg-background dark:hover:bg-background data-[size=default]:h-10 focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
)
export const SelectValue = component(PrimitiveSelectValue, {})
