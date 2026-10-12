import { PasswordInput as PrimitivePasswordInput } from "@/components/ui/password-input"
import { component } from "./component"
export const PasswordInput = component(
  PrimitivePasswordInput,
  {},
  "h-10 rounded-md bg-background text-base shadow-none dark:bg-background focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background md:text-sm",
)
