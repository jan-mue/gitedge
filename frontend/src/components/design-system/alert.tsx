import {
  Alert as PrimitiveAlert,
  AlertDescription as PrimitiveAlertDescription,
  AlertTitle as PrimitiveAlertTitle,
} from "@/components/ui/alert"
import { component } from "./component"
export const Alert = component(PrimitiveAlert, {})
export const AlertTitle = component(PrimitiveAlertTitle, {})
export const AlertDescription = component(PrimitiveAlertDescription, {}, "text-inherit")
