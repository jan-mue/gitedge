import type { Control, FieldPath, FieldValues } from "react-hook-form"
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
import { Input } from "./input"
import { PasswordInput } from "./password-input"
export const Form = PrimitiveForm
export const FormItem = component(PrimitiveFormItem, { inline: "flex items-center gap-3 space-y-0" })
export const FormLabel = component(PrimitiveFormLabel, { regular: "font-normal" })
export const FormControl = component(PrimitiveFormControl, {})
export const FormDescription = component(PrimitiveFormDescription, {})
export const FormMessage = component(PrimitiveFormMessage, { compact: "text-xs" })
export const FormField = PrimitiveFormField

type FormInputFieldProps<T extends FieldValues> = {
  control: Control<T>
  name: FieldPath<T>
  label: string
  placeholder: string
  type?: "text" | "email" | "password"
  required?: boolean
  passwordToggle?: boolean
  testId?: string
}

export const FormInputField = <T extends FieldValues>({
  control,
  name,
  label,
  placeholder,
  type = "text",
  required = false,
  passwordToggle = false,
  testId,
}: FormInputFieldProps<T>) => {
  const Component = passwordToggle ? PasswordInput : Input
  return (
    <FormField
      control={control}
      name={name}
      render={({ field, fieldState }) => (
        <FormItem>
          <FormLabel>
            {label}
            {required && (
              <>
                {" "}
                <span className="text-destructive">*</span>
              </>
            )}
          </FormLabel>
          <FormControl>
            <Component
              {...(passwordToggle ? {} : { type })}
              placeholder={placeholder}
              required={required}
              data-testid={testId}
              aria-invalid={fieldState.invalid}
              {...field}
            />
          </FormControl>
          <FormMessage />
        </FormItem>
      )}
    />
  )
}
