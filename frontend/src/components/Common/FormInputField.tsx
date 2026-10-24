import type { Control, FieldPath, FieldValues } from "react-hook-form"
import {
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
  Input,
  PasswordInput,
} from "@/components/design-system"

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
