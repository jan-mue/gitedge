import { type ComponentProps, useState } from "react"
import {
  Tabs as PrimitiveTabs,
  TabsContent as PrimitiveTabsContent,
  TabsList as PrimitiveTabsList,
  TabsTrigger as PrimitiveTabsTrigger,
} from "@/components/ui/tabs"
import { component } from "./component"
export const Tabs = component(PrimitiveTabs, { spaced: "flex flex-col gap-4" }, "block")
export const TabsList = component(
  PrimitiveTabsList,
  {
    pullRequest:
      "flex h-auto w-full justify-start overflow-x-auto rounded-none border-b border-border bg-transparent p-0",
    branchPicker:
      "flex h-auto w-full items-stretch rounded-none border-b border-border bg-transparent p-0 text-muted-foreground",
  },
  "h-10 rounded-md p-1",
)
const StyledTabsTrigger = component(
  PrimitiveTabsTrigger,
  {
    pullRequest:
      "h-auto shrink-0 flex-none gap-1.5 rounded-none border-0 border-b-2 border-transparent px-3 py-2.5 text-sm font-normal text-muted-foreground shadow-none hover:text-foreground hover:border-border data-[state=active]:border-primary data-[state=active]:bg-transparent data-[state=active]:font-medium data-[state=active]:text-foreground data-[state=active]:shadow-none dark:data-[state=active]:bg-transparent data-[pointer-focus]:focus-visible:ring-0 data-[pointer-focus]:focus-visible:ring-offset-0 sm:px-4",
    branchPicker:
      "flex-1 gap-1.5 rounded-none border-0 px-0 py-2 text-sm font-normal transition-colors hover:text-foreground data-[state=active]:border-b-2 data-[state=active]:border-primary dark:data-[state=active]:border-primary data-[state=active]:bg-transparent data-[state=active]:font-medium data-[state=active]:text-foreground data-[state=active]:shadow-none dark:data-[state=active]:bg-transparent data-[pointer-focus]:outline-none data-[pointer-focus]:focus-visible:ring-0 data-[pointer-focus]:focus-visible:ring-offset-0 data-[pointer-focus]:focus-visible:outline-none",
  },
  "h-auto flex-none rounded-sm border-0 px-3 py-1.5 text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background data-[state=active]:bg-background data-[state=active]:text-foreground dark:data-[state=active]:bg-background",
)
export const TabsTrigger = ({
  appearance,
  onPointerDown,
  onKeyDown,
  onBlur,
  ...props
}: ComponentProps<typeof StyledTabsTrigger>) => {
  const [pointerFocus, setPointerFocus] = useState(false)
  return (
    <StyledTabsTrigger
      {...props}
      appearance={appearance}
      data-pointer-focus={
        (appearance === "branchPicker" || appearance === "pullRequest") && pointerFocus ? "" : undefined
      }
      onPointerDown={(event) => {
        setPointerFocus(true)
        onPointerDown?.(event)
      }}
      onKeyDown={(event) => {
        setPointerFocus(false)
        onKeyDown?.(event)
      }}
      onBlur={(event) => {
        setPointerFocus(false)
        onBlur?.(event)
      }}
    />
  )
}
export const TabsContent = component(
  PrimitiveTabsContent,
  { spaced: "mt-0 space-y-4", pullRequest: "mt-6 space-y-4", branchPicker: "mt-0" },
  "mt-2",
)
