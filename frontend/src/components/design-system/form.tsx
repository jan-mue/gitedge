import {
  Form as PrimitiveForm,
  FormControl as PrimitiveFormControl,
  FormDescription as PrimitiveFormDescription,
  FormField as PrimitiveFormField,
  FormItem as PrimitiveFormItem,
  FormLabel as PrimitiveFormLabel,
  FormMessage as PrimitiveFormMessage,
} from "@/components/ui/form"
import { component } from "./component"
export const Form = PrimitiveForm
export const FormItem = component(PrimitiveFormItem, { inline: "flex items-center gap-3 space-y-0" })
export const FormLabel = component(PrimitiveFormLabel, { regular: "font-normal" })
export const FormControl = component(PrimitiveFormControl, {})
export const FormDescription = component(PrimitiveFormDescription, {})
export const FormMessage = component(PrimitiveFormMessage, { compact: "text-xs" })
export const FormField = PrimitiveFormField
