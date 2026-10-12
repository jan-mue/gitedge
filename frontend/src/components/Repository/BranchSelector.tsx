import { GitBranch } from "lucide-react"
import type { ComponentProps } from "react"
import {
  Button,
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/design-system"

export interface BranchChoice {
  name: string
  is_default?: boolean
  disabled?: boolean
}

type BranchSelectorProps = Pick<
  ComponentProps<typeof SelectTrigger>,
  "id" | "ref" | "onBlur" | "aria-invalid" | "aria-describedby"
> & {
  branches: readonly BranchChoice[]
  value: string
  onValueChange: (branch: string) => void
  name?: string
  label?: string
  placeholder?: string
  appearance?: "compact" | "field" | "filter"
  allLabel?: string
  disabled?: boolean
  loading?: boolean
  error?: boolean
  onRetry?: () => void
  open?: boolean
  defaultOpen?: boolean
  onOpenChange?: (open: boolean) => void
  "data-testid"?: string
  dropdownTestId?: string
}

const BranchSelector = ({
  branches,
  value,
  onValueChange,
  name,
  label = "Switch branch",
  placeholder = "Select a branch",
  appearance = "compact",
  allLabel,
  disabled,
  loading,
  error,
  onRetry,
  open,
  defaultOpen,
  onOpenChange,
  dropdownTestId = "branch-dropdown",
  ...triggerProps
}: BranchSelectorProps) => (
  <div className="min-w-0">
    <Select
      name={name}
      value={value || (allLabel ? "branch:all" : "")}
      onValueChange={(branch) => {
        // Ignore the hidden form control's empty event during option registration.
        if (allLabel && branch === "branch:all") onValueChange("")
        else if (branches.some((choice) => choice.name === branch && !choice.disabled)) onValueChange(branch)
      }}
      disabled={disabled}
      open={open}
      defaultOpen={defaultOpen}
      onOpenChange={onOpenChange}
    >
      <SelectTrigger
        {...triggerProps}
        aria-label={appearance === "filter" ? `Branch: ${value || allLabel || placeholder}` : label}
        data-active={appearance === "filter" && Boolean(value)}
        aria-busy={loading || undefined}
        appearance={appearance === "compact" ? "branch" : appearance === "filter" ? "filter" : "branchField"}
      >
        {appearance !== "filter" && <GitBranch aria-hidden="true" className="size-3.5" />}
        <SelectValue appearance="branch" placeholder={placeholder}>
          {appearance === "filter" ? "Branch" : value || undefined}
        </SelectValue>
      </SelectTrigger>
      <SelectContent align="start" appearance="branch" data-testid={dropdownTestId}>
        <SelectGroup>
          <SelectLabel>Branches</SelectLabel>
          {allLabel && <SelectItem value="branch:all">{allLabel}</SelectItem>}
          {branches.map((branch) => (
            <SelectItem
              key={branch.name}
              value={branch.name}
              textValue={branch.name}
              aria-label={branch.name}
              disabled={branch.disabled}
              data-testid={`branch-option-${branch.name}`}
            >
              <span className="max-w-40 truncate">{branch.name}</span>
              {branch.is_default && (
                <span aria-hidden="true" className="text-xs text-muted-foreground">
                  default
                </span>
              )}
            </SelectItem>
          ))}
          {loading && (
            <SelectItem value="branch:loading" disabled>
              Loading branches…
            </SelectItem>
          )}
          {error && (
            <SelectItem value="branch:error" disabled>
              Unable to load branches.
            </SelectItem>
          )}
          {!loading && !error && branches.length === 0 && (
            <SelectItem value="branch:empty" disabled>
              No branches yet.
            </SelectItem>
          )}
        </SelectGroup>
      </SelectContent>
    </Select>
    {error && (
      <div role="alert" className="mt-2 flex flex-wrap items-center gap-2 text-sm text-destructive">
        <span>Unable to load branches.</span>
        {onRetry && (
          <Button variant="text" size="text" onClick={onRetry}>
            Try again
          </Button>
        )}
      </div>
    )}
  </div>
)

export default BranchSelector
