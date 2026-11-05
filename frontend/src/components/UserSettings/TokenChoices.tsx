import { useId, useState } from "react"
import { Checkbox, Input } from "@/components/design-system"

export const TokenChoices = ({
  label,
  options,
  selected,
  onChange,
  disabled,
  searchable = false,
}: {
  label: string
  options: { value: string; label: string }[]
  selected: string[]
  onChange: (values: string[]) => void
  disabled: boolean
  searchable?: boolean
}) => {
  const id = useId()
  const [query, setQuery] = useState("")
  const visible = options.filter((option) => option.label.toLowerCase().includes(query.toLowerCase()))
  return (
    <fieldset disabled={disabled} className="space-y-2">
      <legend className="mb-2 text-sm font-medium">{label}</legend>
      {searchable && (
        <Input
          aria-label={`Search ${label.toLowerCase()}`}
          placeholder="Find a repository…"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
      )}
      <div className="max-h-64 space-y-3 overflow-y-auto rounded border bg-background p-3">
        {visible.map((option, index) => (
          <label key={option.value} htmlFor={`${id}-${index}`} className="flex items-center gap-3 text-sm">
            <Checkbox
              id={`${id}-${index}`}
              checked={selected.includes(option.value)}
              disabled={disabled}
              onCheckedChange={(checked) =>
                onChange(
                  checked === true ? [...selected, option.value] : selected.filter((value) => value !== option.value),
                )
              }
            />
            <span>{option.label}</span>
          </label>
        ))}
        {!visible.length && <p className="text-sm text-muted-foreground">No matching repositories.</p>}
      </div>
      <p className="text-xs text-muted-foreground">
        {options.filter((option) => selected.includes(option.value)).length} selected
      </p>
    </fieldset>
  )
}
