import {
  Tabs as PrimitiveTabs,
  TabsContent as PrimitiveTabsContent,
  TabsList as PrimitiveTabsList,
  TabsTrigger as PrimitiveTabsTrigger,
} from "@/components/ui/tabs"
import { component } from "./component"
export const Tabs = component(PrimitiveTabs, { spaced: "flex flex-col gap-4" }, "block")
export const TabsList = component(PrimitiveTabsList, {}, "h-10 rounded-md p-1")
export const TabsTrigger = component(
  PrimitiveTabsTrigger,
  {},
  "h-auto flex-none rounded-sm border-0 px-3 py-1.5 text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background data-[state=active]:bg-background data-[state=active]:text-foreground dark:data-[state=active]:bg-background",
)
export const TabsContent = component(PrimitiveTabsContent, { spaced: "mt-0 space-y-4" }, "mt-2")
