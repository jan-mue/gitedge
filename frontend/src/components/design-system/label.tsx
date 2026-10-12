import { Label as PrimitiveLabel } from "@/components/ui/label"
import { component } from "./component"
export const Label = component(PrimitiveLabel, {
  inline: "inline-flex items-center gap-2 font-normal",
  field: "mb-1 block leading-5",
})
