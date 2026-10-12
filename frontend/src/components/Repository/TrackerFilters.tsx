import { CircleDot, Eye, GitMerge, GitPullRequest, HelpCircle, Search } from "lucide-react"
import type { ReactNode } from "react"
import { useRef, useState } from "react"
import { Button, FilterDropdown, Input, Tooltip, TooltipContent, TooltipTrigger } from "@/components/design-system"
import BranchSelector from "./BranchSelector"

interface TrackerItem {
  title: string
  number: number
  state: string
  author_username: string
  created_at: string
  updated_at: string
  base_branch?: string
}

export const useTrackerFilters = <T extends TrackerItem>(items: T[]) => {
  const [search, setSearch] = useState("")
  const [state, setState] = useState("open")
  const [author, setAuthor] = useState("")
  const [branch, setBranch] = useState("")
  const [sort, setSort] = useState("newest")
  const query = search.toLowerCase().trim()
  const filtered = items
    .filter(
      (item) =>
        (state === "all" || (state === "closed" ? item.state !== "open" : item.state === state)) &&
        (!author || item.author_username === author) &&
        (!branch || item.base_branch === branch) &&
        (!query || `${item.title} #${item.number}`.toLowerCase().includes(query)),
    )
    .sort((a, b) => {
      const field = sort === "recently-updated" || sort === "least-updated" ? "updated_at" : "created_at"
      const order = sort === "oldest" || sort === "least-updated" ? 1 : -1
      const difference = Date.parse(a[field]) - Date.parse(b[field])
      return order * (difference || a.number - b.number)
    })
  const authors = Array.from(new Set(items.map((item) => item.author_username).filter(Boolean))).sort()
  const branches = Array.from(
    new Set(
      items
        .map((item) => item.base_branch)
        .filter((value): value is string => typeof value === "string" && value.length > 0),
    ),
  ).sort()
  const hasFilters = !!query || state !== "open" || !!author || !!branch || sort !== "newest"
  const reset = () => {
    setSearch("")
    setState("open")
    setAuthor("")
    setBranch("")
    setSort("newest")
  }
  return {
    search,
    setSearch,
    state,
    setState,
    author,
    setAuthor,
    branch,
    setBranch,
    sort,
    setSort,
    filtered,
    authors,
    branches,
    hasFilters,
    reset,
  }
}

type Filters = ReturnType<typeof useTrackerFilters>

export const TrackerSearch = ({
  filters,
  label,
  children,
}: {
  filters: Filters
  label: string
  children: ReactNode
}) => {
  const input = useRef<HTMLInputElement>(null)
  return (
    <div className="flex flex-wrap items-center gap-2">
      <search className="min-w-40 flex-1" aria-label={`Search ${label}`}>
        <form
          aria-label={`Search ${label}`}
          className="flex min-w-40 flex-1 items-center gap-2"
          onSubmit={(event) => {
            event.preventDefault()
            input.current?.focus()
          }}
        >
          <Input
            ref={input}
            type="search"
            aria-label={`Search ${label}`}
            placeholder={`Search ${label}...`}
            value={filters.search}
            onChange={(event) => filters.setSearch(event.target.value)}
            appearance="trackerSearch"
          />
          <Button type="submit" variant="repository" size="icon-sm" aria-label={`Search ${label}`}>
            <Search aria-hidden="true" />
          </Button>
        </form>
      </search>
      <Tooltip>
        <TooltipTrigger asChild>
          <Button variant="repository" size="icon-sm" aria-label="Search help">
            <HelpCircle aria-hidden="true" />
          </Button>
        </TooltipTrigger>
        <TooltipContent>Search by title or number, then combine filters to narrow the results.</TooltipContent>
      </Tooltip>
      {children}
    </div>
  )
}

const TrackerFilters = ({
  filters,
  openCount,
  closedCount,
  mergedCount,
  totalCount,
  kind,
}: {
  filters: Filters
  openCount: number
  closedCount: number
  mergedCount?: number
  totalCount: number
  kind: "issues" | "pulls"
}) => {
  const Icon = kind === "issues" ? CircleDot : GitPullRequest
  const statuses = [
    { value: "open", label: `${openCount.toLocaleString()} Open`, icon: Icon },
    { value: "closed", label: `${closedCount.toLocaleString()} Closed`, icon: Icon },
    ...(mergedCount === undefined
      ? []
      : [{ value: "merged", label: `${mergedCount.toLocaleString()} Merged`, icon: GitMerge }]),
    { value: "all", label: `${totalCount.toLocaleString()} All`, icon: Eye },
  ]
  return (
    <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-3 border-b border-border bg-secondary px-4 py-2.5 text-sm">
      <fieldset className="flex min-w-0 flex-wrap items-center gap-4" aria-label="Filter by status">
        {statuses.map(({ value, label, icon: StatusIcon }) => (
          <Button
            key={value}
            aria-pressed={filters.state === value}
            onClick={() => filters.setState(value)}
            variant="filter"
            size="text"
          >
            <StatusIcon aria-hidden="true" className="size-4" />
            {label}
          </Button>
        ))}
      </fieldset>
      <div className="flex flex-wrap items-center gap-3">
        <FilterDropdown
          label="Author"
          value={filters.author}
          onChange={filters.setAuthor}
          options={[
            { value: "", label: "All authors" },
            ...filters.authors.map((author) => ({ value: author, label: author })),
          ]}
        />
        {kind === "pulls" && (
          <BranchSelector
            appearance="filter"
            allLabel="All target branches"
            value={filters.branch}
            onValueChange={filters.setBranch}
            branches={filters.branches.map((name) => ({ name }))}
          />
        )}
        <FilterDropdown
          label="Sort"
          value={filters.sort}
          onChange={filters.setSort}
          defaultValue="newest"
          options={[
            { value: "newest", label: "Newest" },
            { value: "oldest", label: "Oldest" },
            { value: "recently-updated", label: "Recently updated" },
            { value: "least-updated", label: "Least recently updated" },
          ]}
        />
        {filters.hasFilters && (
          <Button variant="text" size="text" onClick={filters.reset}>
            Clear filters
          </Button>
        )}
      </div>
    </div>
  )
}
export default TrackerFilters
