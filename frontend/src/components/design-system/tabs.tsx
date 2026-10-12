import {
  Tabs as PrimitiveTabs,
  TabsContent as PrimitiveTabsContent,
  TabsList as PrimitiveTabsList,
  TabsTrigger as PrimitiveTabsTrigger,
} from "@/components/ui/tabs"
import { component } from "./component"
export const Tabs = component(PrimitiveTabs, { spaced: "gap-4" })
export const TabsList = component(PrimitiveTabsList, {})
export const TabsTrigger = component(PrimitiveTabsTrigger, {})
export const TabsContent = component(PrimitiveTabsContent, { spaced: "space-y-4" })
