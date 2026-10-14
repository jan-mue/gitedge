import {
  Card as PrimitiveCard,
  CardAction as PrimitiveCardAction,
  CardContent as PrimitiveCardContent,
  CardDescription as PrimitiveCardDescription,
  CardFooter as PrimitiveCardFooter,
  CardHeader as PrimitiveCardHeader,
  CardTitle as PrimitiveCardTitle,
} from "@/components/ui/card"
import { component } from "./component"
export const Card = component(PrimitiveCard, {}, "gap-0 rounded-lg py-0 shadow-sm")
export const CardHeader = component(PrimitiveCardHeader, {}, "flex flex-col gap-0 space-y-1.5 p-6")
export const CardFooter = component(PrimitiveCardFooter, {})
export const CardTitle = component(PrimitiveCardTitle, {}, "text-2xl font-semibold leading-none tracking-tight")
export const CardAction = component(PrimitiveCardAction, {})
export const CardDescription = component(PrimitiveCardDescription, {})
export const CardContent = component(PrimitiveCardContent, {}, "p-6 pt-0")
