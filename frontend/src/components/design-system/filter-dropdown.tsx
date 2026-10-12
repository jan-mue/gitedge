import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./select"

export interface FilterOption {
  value: string
  label: string
}

export const FilterDropdown = ({
  label,
  options,
  value,
  onChange,
  defaultValue = "",
}: {
  label: string
  options: FilterOption[]
  value: string
  onChange: (value: string) => void
  defaultValue?: string
}) => {
  const index = options.findIndex((option) => option.value === value)
  const selected = options[index]
  return (
    <Select
      value={index < 0 ? "" : String(index)}
      onValueChange={(index) => {
        if (index === "") return
        const option = options[Number(index)]
        if (option) onChange(option.value)
      }}
    >
      <SelectTrigger
        appearance="filter"
        data-active={value !== defaultValue}
        aria-label={`${label}: ${selected?.label ?? "All"}`}
      >
        <SelectValue>{label}</SelectValue>
      </SelectTrigger>
      <SelectContent align="end" appearance="filter" aria-label={label}>
        {options.map((option, index) => (
          <SelectItem key={option.value} value={String(index)}>
            {option.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
