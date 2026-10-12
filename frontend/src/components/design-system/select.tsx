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
export const SelectContent = component(PrimitiveSelectContent, {
  branch: "w-56 min-w-(--radix-select-trigger-width) max-w-[calc(100vw-2rem)] rounded-lg bg-card",
  filter: "w-56 max-w-[calc(100vw-2rem)] rounded-lg",
})
export const SelectGroup = component(PrimitiveSelectGroup, {})
export const SelectItem = component(PrimitiveSelectItem, {})
export const SelectLabel = component(PrimitiveSelectLabel, {})
export const SelectScrollDownButton = component(PrimitiveSelectScrollDownButton, {})
export const SelectScrollUpButton = component(PrimitiveSelectScrollUpButton, {})
export const SelectSeparator = component(PrimitiveSelectSeparator, {})
export const SelectTrigger = component(
  PrimitiveSelectTrigger,
  {
    pagination: "h-8 w-20 data-[size=default]:h-8",
    compact: "w-auto rounded border-border bg-secondary dark:bg-secondary dark:hover:bg-accent data-[size=default]:h-8",
    owner: "rounded border-border bg-secondary dark:bg-secondary dark:hover:bg-accent",
    branch:
      "w-auto max-w-full rounded border-border bg-secondary dark:bg-secondary dark:hover:bg-accent data-[size=default]:h-8",
    branchField: "min-w-0 rounded",
    filter:
      "h-auto w-auto gap-1 rounded-none border-0 bg-transparent p-0 font-normal text-muted-foreground dark:bg-transparent dark:hover:bg-transparent hover:text-foreground data-[size=default]:h-auto data-[active=true]:font-medium data-[active=true]:text-foreground [&_svg]:size-3",
  },
  "w-full bg-background shadow-none dark:bg-background dark:hover:bg-background data-[size=default]:h-10 focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
)
export const SelectValue = component(PrimitiveSelectValue, { branch: "mr-auto min-w-0 max-w-48 truncate" })
