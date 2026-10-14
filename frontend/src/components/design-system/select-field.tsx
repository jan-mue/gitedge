import type { ComponentProps, ReactNode } from "react"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./select"

export interface SelectOption {
  value: string
  label: ReactNode
  disabled?: boolean
}

type SelectFieldProps = Omit<ComponentProps<typeof Select>, "children" | "appearance"> &
  Pick<
    ComponentProps<typeof SelectTrigger>,
    "id" | "aria-label" | "aria-invalid" | "aria-describedby" | "onBlur" | "ref"
  > & {
    options: readonly SelectOption[]
    placeholder?: string
    appearance?: "compact" | "owner" | "pagination"
    "data-testid"?: string
  }

export const SelectField = ({
  options,
  placeholder = "Select an option",
  appearance,
  id,
  ref,
  onBlur,
  "aria-label": label,
  "aria-invalid": invalid,
  "aria-describedby": describedBy,
  "data-testid": testId,
  ...props
}: SelectFieldProps) => (
  <Select
    {...props}
    onValueChange={(value) => {
      // The hidden form control can emit an empty value while options mount.
      if (options.some((option) => option.value === value && !option.disabled)) props.onValueChange?.(value)
    }}
  >
    <SelectTrigger
      id={id}
      ref={ref}
      onBlur={onBlur}
      appearance={appearance}
      aria-label={label}
      aria-invalid={invalid}
      aria-describedby={describedBy}
      data-testid={testId}
    >
      <SelectValue placeholder={placeholder} />
    </SelectTrigger>
    <SelectContent>
      {options.map((option) => (
        <SelectItem key={option.value} value={option.value} disabled={option.disabled}>
          {option.label}
        </SelectItem>
      ))}
      {options.length === 0 && (
        <SelectItem value="select:empty" disabled>
          No options available.
        </SelectItem>
      )}
    </SelectContent>
  </Select>
)
