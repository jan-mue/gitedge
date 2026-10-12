import { Check, Filter, GitBranch, Tag } from "lucide-react"
import { type ComponentProps, type KeyboardEvent, useRef, useState } from "react"
import {
  BranchPicker,
  BranchPickerContent,
  BranchPickerTrigger,
  Button,
  Input,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/design-system"

export interface BranchChoice {
  name: string
  is_default?: boolean
  disabled?: boolean
}
type RefKind = "branch" | "tag"

type BranchSelectorProps = {
  branches: readonly BranchChoice[]
  tags?: readonly BranchChoice[]
  value: string
  kind?: RefKind
  onValueChange: (name: string, kind: RefKind) => void
  label?: string
  disabled?: boolean
  loading?: boolean
  error?: boolean
  onRetry?: () => void
  tagsLoading?: boolean
  tagsError?: boolean
  onRetryTags?: () => void
  open?: boolean
  defaultOpen?: boolean
  onOpenChange?: (open: boolean) => void
  "data-testid"?: string
  dropdownTestId?: string
} & Pick<ComponentProps<typeof Button>, "id">

const BranchSelector = ({
  branches,
  tags = [],
  value,
  kind = "branch",
  onValueChange,
  label = "Switch branch",
  disabled,
  loading,
  error,
  onRetry,
  tagsLoading,
  tagsError,
  onRetryTags,
  open: controlledOpen,
  defaultOpen = false,
  onOpenChange,
  dropdownTestId = "branch-dropdown",
  ...triggerProps
}: BranchSelectorProps) => {
  const [localOpen, setLocalOpen] = useState(defaultOpen)
  const [tab, setTab] = useState<RefKind>(kind)
  const [search, setSearch] = useState("")
  const input = useRef<HTMLInputElement>(null)
  const list = useRef<HTMLDivElement>(null)
  const open = controlledOpen ?? localOpen
  const changeOpen = (next: boolean) => {
    setLocalOpen(next)
    if (next) setTab(kind)
    onOpenChange?.(next)
  }
  const focusOption = (event: KeyboardEvent, fromSearch = false) => {
    if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) return
    // Home/End retain their text-editing behavior in the search input.
    if (fromSearch && (event.key === "Home" || event.key === "End")) return
    const options = Array.from(
      list.current?.querySelectorAll<HTMLButtonElement>('[role="option"]:not(:disabled)') ?? [],
    )
    if (!options.length) return
    event.preventDefault()
    const current = options.indexOf(document.activeElement as HTMLButtonElement)
    const index =
      event.key === "Home"
        ? 0
        : event.key === "End"
          ? options.length - 1
          : event.key === "ArrowUp"
            ? current < 0
              ? options.length - 1
              : (current - 1 + options.length) % options.length
            : (current + 1) % options.length
    options[index]?.focus()
  }
  const items = tab === "branch" ? branches : tags
  const filtered = items.filter((item) => item.name.toLowerCase().includes(search.toLowerCase()))
  const pending = tab === "branch" ? loading : tagsLoading
  const failed = tab === "branch" ? error : tagsError
  const retry = tab === "branch" ? onRetry : onRetryTags
  const plural = tab === "branch" ? "branches" : "tags"

  return (
    <BranchPicker open={open} onOpenChange={changeOpen}>
      <BranchPickerTrigger asChild>
        <Button {...triggerProps} variant="repository" size="branch" disabled={disabled} aria-label={label}>
          <GitBranch aria-hidden="true" className="size-3.5" />
          <span className="min-w-0 max-w-64 truncate">{value || "Select a branch or tag"}</span>
          <span aria-hidden="true" className="text-muted-foreground">
            ▾
          </span>
        </Button>
      </BranchPickerTrigger>
      <BranchPickerContent
        aria-label="Select a branch or tag"
        data-testid={dropdownTestId}
        onOpenAutoFocus={(event) => {
          event.preventDefault()
          input.current?.focus()
        }}
      >
        <div className="border-b border-border p-2">
          <div className="relative">
            <Input
              ref={input}
              type="text"
              aria-label="Filter branch or tag"
              placeholder="Filter branch or tag..."
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              onKeyDown={(event) => focusOption(event, true)}
              appearance="branchSearch"
            />
            <Filter
              aria-hidden="true"
              className="pointer-events-none absolute top-1/2 right-2.5 size-3.5 -translate-y-1/2 text-muted-foreground"
            />
          </div>
        </div>
        <Tabs value={tab} onValueChange={(next) => setTab(next as RefKind)}>
          <TabsList appearance="branchPicker" aria-label="Reference type">
            <TabsTrigger value="branch" appearance="branchPicker">
              <GitBranch aria-hidden="true" className="size-3.5" />
              Branches
            </TabsTrigger>
            <TabsTrigger value="tag" appearance="branchPicker">
              <Tag aria-hidden="true" className="size-3.5" />
              Tags
            </TabsTrigger>
          </TabsList>
          <TabsContent value={tab} appearance="branchPicker">
            <div className="max-h-64 overflow-y-auto">
              {filtered.length > 0 && (
                <div
                  ref={list}
                  role="listbox"
                  aria-label={tab === "branch" ? "Branches" : "Tags"}
                  aria-busy={pending || undefined}
                  onKeyDown={focusOption}
                >
                  {filtered.map((item) => (
                    <Button
                      key={item.name}
                      role="option"
                      aria-label={item.name}
                      aria-selected={item.name === value && tab === kind}
                      disabled={item.disabled}
                      variant="branchItem"
                      size="branchItem"
                      onClick={() => {
                        onValueChange(item.name, tab)
                        changeOpen(false)
                      }}
                      data-testid={`${tab}-option-${item.name}`}
                    >
                      {item.name === value && tab === kind ? (
                        <Check aria-hidden="true" className="size-3.5 shrink-0 text-primary" />
                      ) : (
                        <span aria-hidden="true" className="w-3.5 shrink-0" />
                      )}
                      <span className="truncate">{item.name}</span>
                      {tab === "branch" && item.is_default && (
                        <span
                          aria-hidden="true"
                          className="ml-auto shrink-0 rounded border border-border bg-accent px-1.5 py-0.5 text-xs text-muted-foreground"
                        >
                          default
                        </span>
                      )}
                    </Button>
                  ))}
                </div>
              )}
              {pending && (
                <p role="status" className="px-3 py-4 text-center text-sm text-muted-foreground">
                  Loading {plural}…
                </p>
              )}
              {failed && (
                <p role="alert" className="px-3 py-4 text-center text-sm text-destructive">
                  Unable to load {plural}.
                </p>
              )}
              {!pending && !failed && !filtered.length && (
                <p className="px-3 py-4 text-center text-sm text-muted-foreground">No results found</p>
              )}
            </div>
            {failed && retry && (
              <div className="flex justify-center px-3 pb-3">
                <Button variant="text" size="text" onClick={retry}>
                  Try again
                </Button>
              </div>
            )}
          </TabsContent>
        </Tabs>
      </BranchPickerContent>
    </BranchPicker>
  )
}
export default BranchSelector
