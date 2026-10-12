import { ChevronDown } from "lucide-react"
import { Button } from "./button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "./dropdown-menu"

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
  const selected = options.find((option) => option.value === value)
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="filterMenu"
          size="text"
          data-active={value !== defaultValue}
          aria-label={`${label}: ${selected?.label ?? "All"}`}
        >
          {label}
          <ChevronDown aria-hidden="true" className="size-3" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" appearance="filter" aria-label={label}>
        <DropdownMenuRadioGroup value={value} onValueChange={onChange}>
          {options.map((option) => (
            <DropdownMenuRadioItem key={option.value} value={option.value}>
              {option.label}
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
