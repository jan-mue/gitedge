import { Search } from "lucide-react"
import type { ReactNode } from "react"
import { useState } from "react"

interface TrackerItem {
  title: string
  number: number
  state: string
  author_username: string
  created_at: string
}
export const useTrackerFilters = <T extends TrackerItem>(items: T[]) => {
  const [search, setSearch] = useState("")
  const [state, setState] = useState("all")
  const [author, setAuthor] = useState("")
  const [sort, setSort] = useState("newest")
  const query = search.toLowerCase().trim()
  const filtered = items
    .filter(
      (item) =>
        (state === "all" || (state === "closed" ? item.state !== "open" : item.state === state)) &&
        (!author || item.author_username === author) &&
        (!query || `${item.title} #${item.number}`.toLowerCase().includes(query)),
    )
    .sort((a, b) => (sort === "oldest" ? a.number - b.number : b.number - a.number))
  const authors = Array.from(new Set(items.map((item) => item.author_username).filter(Boolean))).sort()
  return { search, setSearch, state, setState, author, setAuthor, sort, setSort, filtered, authors }
}
interface TrackerFiltersProps {
  filters: ReturnType<typeof useTrackerFilters>
  label: string
  openCount: number
  closedCount: number
  children: ReactNode
}
const TrackerFilters = ({ filters, label, openCount, closedCount, children }: TrackerFiltersProps) => (
  <>
    <div className="flex flex-wrap items-center gap-2">
      <div className="relative min-w-40 flex-1">
        <Search className="pointer-events-none absolute left-3 top-2.5 size-4 text-muted-foreground" />
        <input
          type="search"
          aria-label={`Search ${label}`}
          placeholder={`Search ${label}…`}
          value={filters.search}
          onChange={(event) => filters.setSearch(event.target.value)}
          className="w-full rounded border bg-secondary py-2 pl-9 pr-3 text-sm outline-none focus:ring-1 focus:ring-primary"
        />
      </div>
      {children}
    </div>
    <div className="flex flex-wrap items-center gap-3 rounded border bg-secondary px-4 py-2.5 text-sm">
      {[
        ["all", "All"],
        ["open", `${openCount} Open`],
        ["closed", `${closedCount} Closed`],
      ].map(([value, text]) => (
        <button
          key={value}
          type="button"
          aria-pressed={filters.state === value}
          onClick={() => filters.setState(value)}
          className={
            filters.state === value ? "font-medium text-foreground" : "text-muted-foreground hover:text-foreground"
          }
        >
          {text}
        </button>
      ))}
      <select
        aria-label="Filter by author"
        value={filters.author}
        onChange={(event) => filters.setAuthor(event.target.value)}
        className="rounded border bg-background px-2 py-1 sm:ml-auto"
      >
        <option value="">All authors</option>
        {filters.authors.map((author) => (
          <option key={author} value={author}>
            {author}
          </option>
        ))}
      </select>
      <select
        aria-label="Sort order"
        value={filters.sort}
        onChange={(event) => filters.setSort(event.target.value)}
        className="rounded border bg-background px-2 py-1"
      >
        <option value="newest">Newest</option>
        <option value="oldest">Oldest</option>
      </select>
    </div>
  </>
)
export default TrackerFilters
